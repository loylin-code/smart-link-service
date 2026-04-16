"""HTML callback handler for OAuth2 flow"""
from typing import Dict, Any
from fastapi.responses import HTMLResponse


class HTMLCallbackHandler:
    """HTML 页面跳转回调处理器"""
    
    FRONTEND_URL = "http://localhost:5173"
    FRONTEND_CALLBACK_PATH = "/auth/callback"
    
    def success_response(
        self,
        tokens: Dict[str, Any],
        state: str,
        provider: str
    ) -> HTMLResponse:
        """
        生成成功回调 HTML 页面
        
        页面内容：
        1. 显示成功消息
        2. 自动将 token 存储到 localStorage
        3. 跳转到前端应用
        """
        import json
        tokens_json_str = json.dumps(tokens)
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OAuth Login Successful</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }}
        h1 {{
            margin-bottom: 20px;
            font-size: 2em;
        }}
        p {{
            margin-bottom: 30px;
            opacity: 0.9;
        }}
        .spinner {{
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-top: 4px solid white;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✓ OAuth Login Successful</h1>
        <p>Authenticated via {provider}. Redirecting...</p>
        <div class="spinner"></div>
    </div>
    
    <script>
        // Store tokens in localStorage
        const tokens = {tokens_json_str};
        localStorage.setItem('oauth_access_token', tokens.access_token);
        localStorage.setItem('oauth_refresh_token', tokens.refresh_token || '');
        localStorage.setItem('oauth_token_type', tokens.token_type || 'Bearer');
        localStorage.setItem('oauth_provider', '{provider}');
        localStorage.setItem('oauth_state', '{state}');
        
        // Redirect to frontend
        setTimeout(() => {{
            window.location.href = '{self.FRONTEND_URL}{self.FRONTEND_CALLBACK_PATH}?success=true&provider={provider}';
        }}, 1500);
    </script>
</body>
</html>
"""
        
        return HTMLResponse(content=html, status_code=200, media_type="text/html")
    
    def error_response(
        self,
        error: str,
        error_description: str,
        provider: str
    ) -> HTMLResponse:
        """
        生成错误回调 HTML 页面
        
        页面内容：
        1. 显示错误信息
        2. 提供返回登录页链接
        """
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OAuth Login Failed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #f5576c 0%, #5f2c82 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            max-width: 500px;
        }}
        h1 {{
            margin-bottom: 20px;
            font-size: 2em;
        }}
        .error-message {{
            background: rgba(255, 255, 255, 0.2);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .error-code {{
            font-weight: bold;
            font-size: 1.2em;
            margin-bottom: 10px;
            color: #ffcccc;
        }}
        .error-description {{
            opacity: 0.9;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 30px;
            background: white;
            color: #5f2c82;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✗ OAuth Login Failed</h1>
        <div class="error-message">
            <div class="error-code">{error}</div>
            <div class="error-description">{error_description}</div>
            <div style="margin-top: 10px; opacity: 0.8; font-size: 0.9em;">Provider: {provider}</div>
        </div>
        <a href="{self.FRONTEND_URL}/login" class="btn">Return to Login</a>
    </div>
</body>
</html>
"""
        
        return HTMLResponse(content=html, status_code=200, media_type="text/html")
