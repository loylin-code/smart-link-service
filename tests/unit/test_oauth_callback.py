"""OAuth callback HTML handler tests"""
import pytest
from auth.callbacks.html_callback import HTMLCallbackHandler


class TestHTMLCallbackHandler:
    """Test HTMLCallbackHandler class"""

    def test_success_response(self):
        """Test success response generates HTML with token storage"""
        handler = HTMLCallbackHandler()
        
        tokens = {
            "access_token": "test_access_token_123",
            "refresh_token": "test_refresh_token_456",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        state = "test_state_xyz"
        provider = "google"
        
        response = handler.success_response(tokens, state, provider)
        
        # Verify response type
        assert response.status_code == 200
        assert response.media_type == "text/html"
        
        # Verify HTML content contains token data
        html_content = response.body.decode("utf-8")
        assert "test_access_token_123" in html_content
        assert "test_refresh_token_456" in html_content
        assert "google" in html_content
        assert "localStorage" in html_content
        assert "OAuth Login Successful" in html_content

    def test_error_response(self):
        """Test error response generates HTML with error message"""
        handler = HTMLCallbackHandler()
        
        error = "access_denied"
        error_description = "User denied access"
        provider = "github"
        
        response = handler.error_response(error, error_description, provider)
        
        # Verify response type
        assert response.status_code == 200
        assert response.media_type == "text/html"
        
        # Verify HTML content contains error information
        html_content = response.body.decode("utf-8")
        assert "access_denied" in html_content
        assert "User denied access" in html_content
        assert "github" in html_content
        assert "OAuth Login Failed" in html_content
        assert "Return to Login" in html_content
