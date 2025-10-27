import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.routes.analysis import analysis_bp
from api import get_db, hash_password
from models import User


class TestAnalysisRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-key'
        self.app.register_blueprint(analysis_bp, url_prefix='/api')
        self.client = self.app.test_client()

        # Create a test user for @require_user decorated routes
        with get_db() as db:
            self.test_user = User(
                username='testuser',
                password_hash=hash_password('password123'),
                role='user',
                active=True,
                pending_approval=False
            )
            db.add(self.test_user)
            # Commit is handled automatically by get_db context manager

        # Fetch the user ID after commit
        with get_db() as db:
            user = db.query(User).filter(User.username == 'testuser').first()
            self.test_user_id = user.id if user else None

    @patch('api.routes.analysis.get_db')
    @patch('api.auth_utils.check_analysis_ownership_or_admin')
    @patch('api.routes.analysis.run_ml_analysis')
    @patch('api.routes.analysis.run_traditional_forensics')
    def test_start_analysis_success(self, mock_traditional, mock_ml, mock_ownership, mock_get_db):
        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'
        mock_analysis.video_path = '/test/video.mp4'
        mock_analysis.status = 'created'
        mock_analysis.created_at.isoformat.return_value = '2023-01-01T00:00:00'
        mock_analysis.updated_at.isoformat.return_value = '2023-01-01T00:01:00'

        mock_ownership.return_value = mock_analysis
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.rowcount = 1

        mock_ml.return_value = {
            'models': {
                'xception': {
                    'score': 0.87,
                    'frames': [{'index': 0, 'time': 0.0, 'score': 0.9}],
                    'weights_hash': 'test-hash'
                }
            },
            'video': {'fps': 30, 'width': 1920, 'height': 1080},
            'frames': [],
            'timing_ms': 1000
        }

        mock_traditional.return_value = {
            'ela': {
                'score': 0.65,
                'frames': [{'frame': 'frame_0001.jpg', 'frame_number': 1, 'score': 0.65, 'overlay_url': '/api/analyses/test-analysis-id/forensics/ela/frames/1/overlay'}]
            }
        }

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.post('/api/analyses/test-analysis-id/start',
                                  json={'modules': ['xception'], 'traditional': ['ela']})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['analysis_id'], 'test-analysis-id')
        self.assertEqual(data['status'], 'succeeded')

    @patch('api.routes.analysis.get_db')
    @patch('api.auth_utils.check_analysis_ownership_or_admin')
    def test_start_analysis_no_modules(self, mock_ownership, mock_get_db):
        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_ownership.return_value = mock_analysis
        mock_get_db.return_value.__enter__.return_value = mock_db

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.post('/api/analyses/test-id/start', json={})
        self.assertEqual(response.status_code, 400)

    @patch('api.routes.analysis.get_db')
    @patch('api.auth_utils.check_analysis_ownership_or_admin')
    def test_get_analysis(self, mock_ownership, mock_get_db):
        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'
        mock_analysis.status = 'succeeded'
        mock_analysis.result_json = {'ml': {}, 'traditional': {}}
        mock_analysis.error = None
        mock_analysis.created_at.isoformat.return_value = '2023-01-01T00:00:00'
        mock_analysis.updated_at.isoformat.return_value = '2023-01-01T00:01:00'

        mock_ownership.return_value = mock_analysis
        mock_get_db.return_value.__enter__.return_value = mock_db

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.get('/api/analyses/test-analysis-id')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['analysis_id'], 'test-analysis-id')

    @patch('storage.DATA_ROOT')
    @patch('api.routes.analysis.get_db')
    @patch('api.auth_utils.check_analysis_ownership_or_admin')
    @patch('api.routes.analysis.extract_single_frame')
    @patch('api.routes.analysis.run_ela')
    def test_analyze_frame(self, mock_ela, mock_extract, mock_ownership, mock_get_db, mock_data_root):
        # Mock DATA_ROOT path operations
        mock_frames_dir = MagicMock()
        mock_frames_dir.mkdir = MagicMock()
        mock_method_dir = MagicMock()
        mock_method_dir.mkdir = MagicMock()

        def data_root_truediv(path):
            if 'frames' in str(path):
                return mock_frames_dir
            else:
                return mock_method_dir

        mock_data_root.__truediv__ = MagicMock(side_effect=data_root_truediv)
        mock_frames_dir.__truediv__ = MagicMock(return_value='/fake/frame_0042.jpg')

        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'
        mock_analysis.video_path = '/test/video.mp4'
        mock_analysis.result_json = {}  # Initialize as empty dict for merge logic

        mock_ownership.return_value = mock_analysis
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_extract.return_value = None
        # run_ela now returns single-frame result with raw score
        mock_ela.return_value = {
            'mode': 'single_frame',
            'frame': 'frame_0042.jpg',
            'score': 2.5  # Raw score
        }

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.post('/api/analyses/test-analysis-id/frames/42/forensics',
                                  json={'methods': ['ela']})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['frame_number'], 42)
        self.assertIn('results', data)
        self.assertIn('ela', data['results'])

    @patch('api.routes.analysis._get_video_metadata')
    def test_get_video_metadata(self, mock_metadata):
        mock_metadata.return_value = {
            'fps': 30.0,
            'frame_count': 900,
            'duration_sec': 30.0,
            'width': 1920,
            'height': 1080
        }

        from api.routes.analysis import _get_video_metadata
        result = _get_video_metadata('/test/video.mp4')
        self.assertIsInstance(result, dict)
        self.assertIn('fps', result)


if __name__ == '__main__':
    unittest.main()