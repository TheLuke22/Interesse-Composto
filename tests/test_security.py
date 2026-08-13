"""
Security tests ensuring no unauthorized admin bypass via ?admin=1.
"""
import unittest
from unittest.mock import patch
import monetization_engine


class TestSecurity(unittest.TestCase):

    def test_admin_bypass_blocked(self):
        # Simulate query params with ?admin=1 (should NOT grant admin access)
        with patch("streamlit.session_state", {}), patch("streamlit.query_params", {"admin": "1"}):
            is_admin = monetization_engine.check_is_admin()
            self.assertFalse(is_admin)

    def test_admin_valid_secret_key(self):
        # Simulate query params with ?key=admin2026 (matching default ADMIN_SECRET_KEY)
        with patch("streamlit.session_state", {}), patch("streamlit.query_params", {"key": "admin2026"}):
            is_admin = monetization_engine.check_is_admin()
            self.assertTrue(is_admin)

    def test_admin_wrong_secret_key(self):
        # Simulate query params with ?key=wrong_key
        with patch("streamlit.session_state", {}), patch("streamlit.query_params", {"key": "wrong_key_123"}):
            is_admin = monetization_engine.check_is_admin()
            self.assertFalse(is_admin)


if __name__ == "__main__":
    unittest.main()
