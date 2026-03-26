import unittest
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app import create_app


class LoginDatabaseFailureTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_login_returns_service_unavailable_when_database_fails(self):
        with patch("app.routes.auth.User.query") as query:
            query.filter_by.return_value.first.side_effect = SQLAlchemyError("db down")

            response = self.client.post(
                "/login",
                data={"username": "demo", "password": "secret"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn(
            b"La base de donnees des utilisateurs est indisponible.",
            response.data,
        )


if __name__ == "__main__":
    unittest.main()