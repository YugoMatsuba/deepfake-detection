import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.routes.traditional_forensics import bp_forensics


class TestTraditionalForensicsRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.register_blueprint(bp_forensics, url_prefix='/api/forensics')
        self.client = self.app.test_client()

    @patch('api.routes.traditional_forensics.extract_frames')
    def test_extract_frames_success(self, mock_extract):
        mock_extract.return_value = ['frame1.jpg', 'frame2.jpg', 'frame3.jpg']

        response = self.client.post('/api/forensics/extract_frames',
                                  json={'video_path': 'test/video.mp4'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data['frames']), 3)
        self.assertIn('message', data)

    def test_extract_frames_no_path(self):
        response = self.client.post('/api/forensics/extract_frames', json={})
        self.assertEqual(response.status_code, 400)

    @patch('api.routes.traditional_forensics.extract_frames')
    def test_extract_frames_file_not_found(self, mock_extract):
        mock_extract.side_effect = FileNotFoundError("Video file not found")

        response = self.client.post('/api/forensics/extract_frames',
                                  json={'video_path': 'nonexistent/video.mp4'})

        self.assertEqual(response.status_code, 404)

    @patch('api.routes.traditional_forensics.run_ela')
    def test_ela_analysis_success(self, mock_ela):
        mock_ela.return_value = {
            'score': 0.75,
            'frames': [{'frame': 'frame1.jpg', 'score': 0.8}]
        }

        response = self.client.post('/api/forensics/ela_analysis',
                                  json={'input_path': 'test/frames'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('result', data)
        self.assertEqual(data['result']['score'], 0.75)

    def test_ela_analysis_no_input_path(self):
        response = self.client.post('/api/forensics/ela_analysis', json={})
        self.assertEqual(response.status_code, 400)

    @patch('api.routes.traditional_forensics.run_noise_analysis')
    def test_noise_analysis_success(self, mock_noise):
        mock_noise.return_value = {
            'confidence': 0.68,
            'frames': [{'frame': 'frame1.jpg', 'confidence': 0.7}]
        }

        response = self.client.post('/api/forensics/noise_analysis',
                                  json={'input_path': 'test/frames'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('result', data)

    @patch('api.routes.traditional_forensics.run_lbp_analysis')
    def test_lbp_analysis_success(self, mock_lbp):
        mock_lbp.return_value = {
            'score': 0.81,
            'frames': [{'frame': 'frame1.jpg', 'score': 0.85}]
        }

        response = self.client.post('/api/forensics/lbp_analysis',
                                  json={'input_path': 'test/frames', 'top_percent': 15})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('result', data)

    @patch('api.routes.traditional_forensics.run_lbp_analysis')
    def test_analyze_frame_lbp(self, mock_lbp):
        mock_lbp.return_value = {
            'score': 0.79,
            'lbp_image': 'base64-encoded-image'
        }

        frame_data = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/"

        response = self.client.post('/api/forensics/analyze_frame',
                                  json={
                                      'frame_data': frame_data,
                                      'analysis_type': 'lbp',
                                      'frame_number': 42
                                  })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['frame_number'], 42)
        self.assertEqual(data['analysis_type'], 'lbp')

    def test_analyze_frame_no_frame_data(self):
        response = self.client.post('/api/forensics/analyze_frame',
                                  json={'analysis_type': 'lbp'})

        self.assertEqual(response.status_code, 400)

    def test_analyze_frame_unsupported_type(self):
        frame_data = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/"

        response = self.client.post('/api/forensics/analyze_frame',
                                  json={
                                      'frame_data': frame_data,
                                      'analysis_type': 'unsupported'
                                  })

        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()