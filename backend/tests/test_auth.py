import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.routes.auth import bp
from models import User, AuditLog


class TestAuthRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-key'
        self.app.register_blueprint(bp, url_prefix='/api/auth')
        self.client = self.app.test_client()

    @patch('api.routes.auth.get_db')
    @patch('api.routes.auth.hash_password')
    def test_register_first_user(self, mock_hash_password, mock_get_db):
        mock_db = MagicMock()
        mock_db.query().count.return_value = 0
        mock_db.query().filter().first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_hash_password.return_value = 'hashed_password'

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = 'admin'
        mock_user.role = 'admin'
        mock_user.active = True
        mock_db.refresh.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None

        response = self.client.post('/api/auth/register',
                                  json={'username': 'admin', 'password': 'password123'})

        self.assertEqual(response.status_code, 201)

    @patch('api.routes.auth.get_db')
    def test_register_missing_payload(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        response = self.client.post('/api/auth/register', json={})
        self.assertEqual(response.status_code, 400)

    @patch('api.routes.auth.get_db')
    @patch('api.routes.auth.verify_password')
    def test_login_success(self, mock_verify_password, mock_get_db):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = 'testuser'
        mock_user.role = 'user'  # Updated from 'investigator' to 'user'
        mock_user.active = True
        mock_user.pending_approval = False  # User is approved
        mock_user.password_hash = 'hashed_password'

        mock_db.query().filter().first.return_value = mock_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_verify_password.return_value = True

        with self.app.test_request_context():
            response = self.client.post('/api/auth/login',
                                      json={'username': 'testuser', 'password': 'password123'})

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('user', data)
            self.assertEqual(data['user']['username'], 'testuser')

    @patch('api.routes.auth.get_db')
    def test_login_invalid_credentials(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db

        response = self.client.post('/api/auth/login',
                                  json={'username': 'nonexistent', 'password': 'wrong'})

        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data['error'], 'invalid_credentials')

    @patch('api.routes.auth.get_db')
    def test_logout(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        response = self.client.post('/api/auth/logout')
        self.assertEqual(response.status_code, 204)

    @patch('api.routes.auth.get_db')
    def test_me_authenticated(self, mock_get_db):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = 'testuser'
        mock_user.role = 'user'  # Updated from 'investigator' to 'user'
        mock_user.active = True
        mock_user.pending_approval = False  # User is approved

        mock_db.get.return_value = mock_user
        mock_get_db.return_value.__enter__.return_value = mock_db

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['user']['username'], 'testuser')

    @patch('api.routes.auth.get_db')
    def test_me_unauthenticated(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db

        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()