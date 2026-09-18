import unittest
import tempfile
import shutil
from pathlib import Path

from src.services.database import init_database
from src.services.auth.auth_service import AuthService
from src.services.auth.types import UserSignupRequest, UserSigninRequest


class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_auth.db"
        init_database(db_path=self.db_path)
        self.auth = AuthService(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_auth_service_signup_and_signin(self):
        res = self.auth.signup(UserSignupRequest(email="solidadmin@cyber.io", password="securepassword123"))
        self.assertIsNotNone(res.token)
        self.assertEqual(res.user.email, "solidadmin@cyber.io")
        self.assertFalse(res.user.has_api_key)

        with self.assertRaises(ValueError):
            self.auth.signup(UserSignupRequest(email="solidadmin@cyber.io", password="anotherpassword"))

        signin_res = self.auth.signin(UserSigninRequest(email="solidadmin@cyber.io", password="securepassword123"))
        self.assertIsNotNone(signin_res.token)
        self.assertEqual(signin_res.user.id, res.user.id)

        with self.assertRaises(PermissionError):
            self.auth.signin(UserSigninRequest(email="solidadmin@cyber.io", password="wrongpassword"))

        updated_user = self.auth.set_user_api_key(res.user.id, "AIzaSySecretLongKey987654321")
        self.assertTrue(updated_user.has_api_key)
        self.assertEqual(updated_user.api_key_preview, "AIzaSy...4321")

        cleared_user = self.auth.delete_user_api_key(res.user.id)
        self.assertFalse(cleared_user.has_api_key)
        self.assertIsNone(cleared_user.api_key_preview)


if __name__ == "__main__":
    unittest.main()
