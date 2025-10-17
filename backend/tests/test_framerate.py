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
        self.app.register_blueprint(frame_rate_bp, url_prefix='/api')
        self.client = self.app.test_client()

    @patch('api.routes.framerate.get_all_videos')
    @patch('api.routes.framerate.cv2.VideoCapture')
    @patch('api.routes.framerate.Path')
    def test_get_frame_rate_success(self, mock_path, mock_cv2, mock_get_all_videos):
        # Mock the response from get_all_videos
        mock_response = MagicMock()
        mock_response.get_json.return_value = [
            {
                'id': 'test-id-1',
                'path': '/test/video1.mp4',
                'original_name': 'video1.mp4'
            },
            {
                'id': 'test-id-2',
                'path': '/test/video2.mp4',
                'original_name': 'video2.mp4'
            }
        ]
        mock_get_all_videos.return_value = mock_response

        # Mock Path existence check
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Mock OpenCV video capture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 29.97  # Mock FPS
        mock_cv2.return_value = mock_cap

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['video_id'], 'test-id-2')  # Should get the latest (last) video
        self.assertEqual(data['original_name'], 'video2.mp4')
        self.assertEqual(data['frame_rate'], 29.97)

    @patch('api.routes.framerate.get_all_videos')
    def test_get_frame_rate_no_videos(self, mock_get_all_videos):
        mock_response = MagicMock()
        mock_response.get_json.return_value = []
        mock_get_all_videos.return_value = mock_response

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'No videos found')

    @patch('api.routes.framerate.get_all_videos')
    def test_get_frame_rate_no_videos_none(self, mock_get_all_videos):
        mock_response = MagicMock()
        mock_response.get_json.return_value = None
        mock_get_all_videos.return_value = mock_response

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'No videos found')

    @patch('api.routes.framerate.get_all_videos')
    @patch('api.routes.framerate.Path')
    def test_get_frame_rate_video_file_not_found(self, mock_path, mock_get_all_videos):
        mock_response = MagicMock()
        mock_response.get_json.return_value = [
            {
                'id': 'test-id-1',
                'path': '/nonexistent/video.mp4',
                'original_name': 'video.mp4'
            }
        ]
        mock_get_all_videos.return_value = mock_response

        # Mock Path existence check to return False
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'Video file not found')

    @patch('api.routes.framerate.get_all_videos')
    @patch('api.routes.framerate.cv2.VideoCapture')
    @patch('api.routes.framerate.Path')
    def test_get_frame_rate_video_cannot_open(self, mock_path, mock_cv2, mock_get_all_videos):
        mock_response = MagicMock()
        mock_response.get_json.return_value = [
            {
                'id': 'test-id-1',
                'path': '/test/corrupted_video.mp4',
                'original_name': 'corrupted_video.mp4'
            }
        ]
        mock_get_all_videos.return_value = mock_response

        # Mock Path existence check
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Mock OpenCV video capture failure
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.return_value = mock_cap

        response = self.client.get('/api/framerate')

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data['error'], 'Could not open video')


if __name__ == '__main__':
    unittest.main()