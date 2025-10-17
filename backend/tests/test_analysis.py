import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.routes.analysis import analysis_bp


class TestAnalysisRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-key'
        self.app.register_blueprint(analysis_bp, url_prefix='/api')
        self.client = self.app.test_client()

    @patch('api.routes.analysis.get_db')
    @patch('api.routes.analysis.check_analysis_ownership')
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
            'ela': {'score': 0.65, 'overlay': 'base64-data'}
        }

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        response = self.client.post('/api/analyses/test-analysis-id/start',
                                  json={'modules': ['xception'], 'traditional': ['ela']})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['analysis_id'], 'test-analysis-id')
        self.assertEqual(data['status'], 'succeeded')

    @patch('api.routes.analysis.get_db')
    @patch('api.routes.analysis.check_analysis_ownership')
    def test_start_analysis_no_modules(self, mock_ownership, mock_get_db):
        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_ownership.return_value = mock_analysis
        mock_get_db.return_value.__enter__.return_value = mock_db

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        response = self.client.post('/api/analyses/test-id/start', json={})
        self.assertEqual(response.status_code, 400)

    @patch('api.routes.analysis.get_db')
    @patch('api.routes.analysis.check_analysis_ownership')
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
            sess['user_id'] = 1

        response = self.client.get('/api/analyses/test-analysis-id')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['analysis_id'], 'test-analysis-id')

    @patch('api.routes.analysis.get_db')
    @patch('api.routes.analysis.check_analysis_ownership')
    @patch('api.routes.analysis.extract_single_frame')
    @patch('api.routes.analysis.run_ela')
    @patch('api.routes.analysis.transform_ela_result')
    def test_analyze_frame(self, mock_transform, mock_ela, mock_extract, mock_ownership, mock_get_db):
        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'
        mock_analysis.video_path = '/test/video.mp4'

        mock_ownership.return_value = mock_analysis
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_extract.return_value = None
        mock_ela.return_value = {'score': 0.75}
        mock_transform.return_value = {
            'score': 0.75,
            'frames': [{'frame_number': 42}]
        }

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        response = self.client.post('/api/analyses/test-analysis-id/frames/42/forensics',
                                  json={'methods': ['ela']})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['frame_number'], 42)

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