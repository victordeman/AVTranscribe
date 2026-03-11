import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add backend to path to import src
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.utils import send_error_email

class TestEmailAlert(unittest.TestCase):
    @patch("smtplib.SMTP")
    @patch("ssl.create_default_context")
    def test_send_error_email_success(self, mock_ssl, mock_smtp):
        # Setup environment variables
        os.environ["SMTP_HOST"] = "smtp.test.com"
        os.environ["SMTP_PORT"] = "587"
        os.environ["SMTP_USER"] = "user@test.com"
        os.environ["SMTP_PASSWORD"] = "password"
        os.environ["ALERT_EMAIL_TO"] = "admin@test.com"

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        send_error_email("test-task-id", "Test error message")

        # Verify SMTP interactions
        mock_smtp.assert_called_with("smtp.test.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with("user@test.com", "password")
        mock_server.send_message.assert_called_once()

        # Verify message content
        args, kwargs = mock_server.send_message.call_args
        msg = args[0]
        self.assertEqual(msg["To"], "admin@test.com")
        self.assertEqual(msg["From"], "user@test.com")
        self.assertIn("test-task-id", msg["Subject"])
        self.assertIn("Test error message", msg.get_content())

    @patch("src.utils.logger")
    def test_send_error_email_missing_config(self, mock_logger):
        # Clear environment variables
        for key in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO"]:
            if key in os.environ:
                del os.environ[key]

        send_error_email("test-task-id", "Test error message")

        mock_logger.warning.assert_called_with("SMTP configuration incomplete. Skipping error email.", task_id="test-task-id")

if __name__ == "__main__":
    unittest.main()
