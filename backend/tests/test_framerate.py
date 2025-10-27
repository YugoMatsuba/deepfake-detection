import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.routes.framerate import frame_rate_bp


class TestFrameRateRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.register_blueprint(frame_rate_bp, url_prefix='/api')
        self.client = self.app.test_client()
        self.test_user_id = 1

    @patch('api.routes.framerate.get_db')
    @patch('api.routes.framerate.DATA_ROOT')
    @patch('api.routes.framerate.cv2.VideoCapture')
    @patch('api.auth_utils.current_user')
    def test_get_frame_rate_success(self, mock_current_user, mock_cv2, mock_data_root, mock_get_db):
        # Mock database and user
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = self.test_user_id
        mock_user.role = 'user'
        mock_current_user.return_value = mock_user

        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'
        mock_analysis.original_filename = 'test_video.mp4'

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_analysis]
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock filesystem
        mock_video_dir = MagicMock()
        mock_video_dir.exists.return_value = True
        mock_video_file = MagicMock()
        mock_video_file.name = 'video.mp4'
        mock_video_dir.glob.return_value = [mock_video_file]
        mock_data_root.__truediv__.return_value = mock_video_dir

        # Mock OpenCV video capture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 29.97  # Mock FPS
        mock_cv2.return_value = mock_cap

        # Set session for auth
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['video_id'], 'test-analysis-id')
        self.assertEqual(data['original_name'], 'test_video.mp4')
        self.assertEqual(data['frame_rate'], 29.97)

    @patch('api.routes.framerate.get_db')
    @patch('api.auth_utils.current_user')
    def test_get_frame_rate_no_videos(self, mock_current_user, mock_get_db):
        # Mock database with no analyses
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = self.test_user_id
        mock_user.role = 'user'
        mock_current_user.return_value = mock_user

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Set session for auth
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'No videos found')

    @patch('api.routes.framerate.get_db')
    @patch('api.routes.framerate.DATA_ROOT')
    @patch('api.auth_utils.current_user')
    def test_get_frame_rate_video_file_not_found(self, mock_current_user, mock_data_root, mock_get_db):
        # Mock database and user
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = self.test_user_id
        mock_user.role = 'user'
        mock_current_user.return_value = mock_user

        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_analysis]
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock filesystem - video directory doesn't exist
        mock_video_dir = MagicMock()
        mock_video_dir.exists.return_value = False
        mock_data_root.__truediv__.return_value = mock_video_dir

        # Set session for auth
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'No valid video files found')

    @patch('api.routes.framerate.get_db')
    @patch('api.routes.framerate.DATA_ROOT')
    @patch('api.routes.framerate.cv2.VideoCapture')
    @patch('api.auth_utils.current_user')
    def test_get_frame_rate_video_cannot_open(self, mock_current_user, mock_cv2, mock_data_root, mock_get_db):
        # Mock database and user
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = self.test_user_id
        mock_user.role = 'user'
        mock_current_user.return_value = mock_user

        mock_analysis = MagicMock()
        mock_analysis.id = 'test-analysis-id'

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_analysis]
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock filesystem
        mock_video_dir = MagicMock()
        mock_video_dir.exists.return_value = True
        mock_video_file = MagicMock()
        mock_video_dir.glob.return_value = [mock_video_file]
        mock_data_root.__truediv__.return_value = mock_video_dir

        # Mock OpenCV video capture failure
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.return_value = mock_cap

        # Set session for auth
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'No valid video files found')


if __name__ == '__main__':
    unittest.main()
