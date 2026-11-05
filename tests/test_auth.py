"""Run with: python -m unittest discover -s tests -v."""

from contextlib import closing
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from spelling_game import create_app


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        class Config:
            TESTING = True
            SECRET_KEY = "test-only-key"
            AUTH_DATABASE = str(Path(self.directory.name) / "accounts.sqlite3")
        self.app = create_app(Config)
        self.client = self.app.test_client()
        self.database = Config.AUTH_DATABASE

    def token(self, path, prefix):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        return re.search(r'name="' + prefix + r'-csrf_token"[^>]*value="([^"]+)"', html).group(1)

    def signup(self, **changes):
        data = {"signup-name": "Test Player", "signup-email": " PLAYER@Example.com ",
                "signup-password": "correct horse battery", "signup-confirm_password": "correct horse battery",
                "signup-csrf_token": self.token("/signup", "signup")}
        data.update(changes)
        return self.client.post("/signup", data=data)

    def logout(self):
        html = self.client.get("/").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        return self.client.post("/logout", data={"csrf_token": token})

    def test_signup_login_logout_and_protected_pages(self):
        self.assertEqual(self.client.get('/game').status_code, 302)
        self.assertEqual(self.signup().status_code, 302)
        with closing(sqlite3.connect(self.database)) as db:
            email, password_hash, role = db.execute('SELECT email, password_hash, role FROM users').fetchone()
        self.assertEqual(email, 'player@example.com')
        self.assertEqual(role, 'player')
        self.assertNotEqual(password_hash, 'correct horse battery')
        self.assertEqual(self.client.get('/game').status_code, 200)
        self.assertEqual(self.client.get('/words').status_code, 403)
        self.assertEqual(self.logout().status_code, 302)
        token = self.token('/login', 'login')
        self.assertEqual(self.client.post('/login', data={'login-csrf_token': token, 'login-email': email, 'login-password': 'wrong'}).status_code, 401)
        token = self.token('/login', 'login')
        response = self.client.post('/login', data={'login-csrf_token': token, 'login-email': email.upper(), 'login-password': 'correct horse battery', 'login-remember': 'y', 'next': '//evil.example'})
        self.assertEqual(response.location, '/')
        with self.client.session_transaction() as session:
            self.assertTrue(session.permanent)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_validation_duplicate_and_csrf(self):
        self.assertEqual(self.client.post('/signup', data={}).status_code, 400)
        self.assertEqual(self.signup(**{'signup-email': 'not-an-email'}).status_code, 400)
        self.assertEqual(self.signup(**{'signup-confirm_password': 'different'}).status_code, 400)
        self.assertEqual(self.signup(**{'signup-password': 'short', 'signup-confirm_password': 'short'}).status_code, 400)
        self.assertEqual(self.signup().status_code, 302)
        self.assertEqual(self.client.post('/logout').status_code, 400)
        self.logout()
        response = self.signup()
        self.assertEqual(response.status_code, 409)
        self.assertIn(b'already exists', response.data)

    def test_safe_redirect_and_database_role(self):
        response = self.signup(next='/game?difficulty=hard', role='admin')
        self.assertEqual(response.location, '/game?difficulty=hard')
        with self.client.session_transaction() as session:
            user_id = session['user_id']
            session['role'] = 'admin'
        self.assertEqual(self.client.get('/words').status_code, 403)
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
            db.commit()
        self.assertEqual(self.client.get('/words').status_code, 200)
        with closing(sqlite3.connect(self.database)) as db:
            db.execute('DELETE FROM users WHERE id = ?', (user_id,))
            db.commit()
        self.assertEqual(self.client.get('/game').status_code, 302)


if __name__ == '__main__':
    unittest.main()
