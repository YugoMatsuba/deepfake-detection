import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from werkzeug.datastructures import FileStorage
import io
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.routes.video_upload import video_bp
from api import get_db, hash_password
from models import User


class TestVideoUploadRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-key'
        self.app.register_blueprint(video_bp, url_prefix='/api')
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
            db.flush()  # Get the ID without committing
            self.test_user_id = self.test_user.id

    @patch('api.routes.video_upload.get_db')
    @patch('api.routes.video_upload.save_video_for_analysis')
    @patch('api.routes.video_upload.probe_video_metadata')
    def test_upload_video_success(self, mock_probe, mock_save, mock_get_db):
        mock_db = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_save.return_value = ('/test/path/video.mp4', 'sha256-hash')
        mock_probe.return_value = {'fps': 30, 'width': 1920, 'height': 1080}

        data = b'fake video data'
        file_obj = FileStorage(
            stream=io.BytesIO(data),
            filename='test_video.mp4',
            content_type='video/mp4'
        )

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.post('/api/videos',
                                  data={'file': file_obj},
                                  content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn('analysis_id', data)
        self.assertIn('video_sha256', data)

    def test_upload_video_no_file(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.post('/api/videos')
        self.assertEqual(response.status_code, 400)

    def test_upload_video_unsupported_mimetype(self):
        data = b'fake data'
        file_obj = FileStorage(
            stream=io.BytesIO(data),
            filename='test.txt',
            content_type='text/plain'
        )

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.post('/api/videos',
                                  data={'file': file_obj},
                                  content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400)

    @patch('api.routes.video_upload.DATA_ROOT')
    def test_list_videos(self, mock_data_root):
        mock_analysis_dir = MagicMock()
        mock_analysis_dir.name = 'test-analysis-id'
        mock_analysis_dir.is_dir.return_value = True
        mock_analysis_dir.glob.return_value = ['/test/video.mp4']

        mock_data_root.exists.return_value = True
        mock_data_root.iterdir.return_value = [mock_analysis_dir]

        response = self.client.get('/api/videos/all')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)

    @patch('api.routes.video_upload.DATA_ROOT')
    @patch('api.routes.video_upload.send_file')
    def test_get_video(self, mock_send_file, mock_data_root):
        mock_video_dir = MagicMock()
        mock_video_dir.exists.return_value = True
        mock_video_dir.glob.return_value = ['/test/video.mp4']
        mock_data_root.__truediv__.return_value = mock_video_dir

        mock_send_file.return_value = 'video content'

        response = self.client.get('/api/videos/test-analysis-id')
        mock_send_file.assert_called_once()

    @patch('api.routes.video_upload.get_db')
    @patch('api.routes.video_upload.DATA_ROOT')
    def test_get_analysis_video_not_found(self, mock_data_root, mock_get_db):
        mock_db = MagicMock()
        # Mock database query to return None (analysis not found)
        mock_db.query().filter().first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_video_dir = MagicMock()
        mock_video_dir.exists.return_value = False
        mock_data_root.__truediv__.return_value = mock_video_dir

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.get('/api/analyses/nonexistent/video')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()