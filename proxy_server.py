"""
Minimal Proxy Server — सिर्फ WebApp serve करने के लिए
"""
import logging
from flask import Flask, render_template_string, request

from config import PROXY_HOST, PROXY_PORT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

WEBAPP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Domino's India 🍕</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #006491;
            height: 100vh;
            overflow: hidden;
        }
        .header {
            background: #006491;
            color: white;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 14px;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        iframe {
            width: 100%;
            height: calc(100vh - 50px);
            border: none;
            background: white;
        }
        .back-btn {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
        }
        .back-btn:hover { background: rgba(255,255,255,0.3); }
    </style>
</head>
<body>
    <div class="header">
        <span>🍕 Domino's India</span>
        <button class="back-btn" onclick="goBack()">← Back</button>
    </div>
    <iframe id="dominosFrame" 
            src="https://m.dominos.co.in/postorder-ui/login"
            allow="payment; clipboard-read; clipboard-write"
            sandbox="allow-scripts allow-forms allow-same-origin allow-popups">
    </iframe>
    <script>
        function goBack() {
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.close();
            } else {
                history.back();
            }
        }
        
        // Initialize Telegram WebApp
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
        }
        
        // Try to maintain session
        const frame = document.getElementById('dominosFrame');
        let retryCount = 0;
        
        frame.onload = function() {
            console.log('Frame loaded:', frame.contentWindow.location.href);
            retryCount = 0;
        };
        
        frame.onerror = function() {
            retryCount++;
            if (retryCount > 3) {
                frame.src = 'https://m.dominos.co.in/';
            }
        };
    </script>
</body>
</html>
"""

@app.route("/webapp")
def webapp():
    return render_template_string(WEBAPP_HTML)

@app.route("/")
def home():
    return render_template_string(WEBAPP_HTML)

if __name__ == "__main__":
    logger.info(f"🚀 WebApp server on {PROXY_HOST}:{PROXY_PORT}")
    app.run(host=PROXY_HOST, port=PROXY_PORT, debug=False)
