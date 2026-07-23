#!/usr/bin/env python3
"""
Flask Proxy Server
==================
Acts as a Telegram WebApp server that:
1. Serves the WebApp mini window
2. Acts as a reverse proxy to Domino's India
3. Injects session cookies so the user stays logged in

How it works:
- User clicks an account in My Account → Telegram opens WebApp
- WebApp loads from our server
- Our server fetches Domino's page WITH the user's cookies
- Serves it back to the user (with adjusted URLs)
"""
import base64
import json
import logging
import re

import requests
from flask import Flask, request, Response, render_template_string, redirect

from config import PROXY_HOST, PROXY_PORT, DOMINOS_BASE_URL
from session_store import session_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def get_user_from_request() -> int | None:
    """
    Try to extract Telegram user ID from WebApp init data.
    Telegram WebApp passes user data in the query string.
    """
    # From query param
    user_id = request.args.get("tg_id")
    if user_id:
        return int(user_id)

    # From Telegram WebApp initData
    init_data = request.args.get("tgWebAppData", "")
    if init_data:
        # Parse the init data
        try:
            import urllib.parse
            parsed = urllib.parse.parse_qs(init_data)
            user_json = parsed.get("user", [None])[0]
            if user_json:
                user_obj = json.loads(user_json)
                return user_obj.get("id")
        except Exception:
            pass

    return None


@app.route("/open-account")
def open_account():
    """
    Open Domino's account in mini window.
    Injects cookies so user is already logged in.
    """
    phone = request.args.get("phone", "")
    user_id = get_user_from_request()

    if not user_id:
        # Fallback: show phone input or error
        return render_error("User not identified. Please open from Telegram bot.")

    # Get saved cookies
    cookies = session_store.get_session_cookies(user_id, phone)
    if not cookies:
        return render_error(
            f"No session found for {phone}. Please login again from bot."
        )

    # Set active account
    session_store.set_active_account(user_id, phone)

    # Redirect to the proxy handler that injects cookies
    cookie_b64 = base64.b64encode(json.dumps(cookies).encode()).decode()
    return redirect(
        f"/proxy/?url=/postorder-ui/&cookie={cookie_b64}&phone={phone}"
    )


@app.route("/open-cart")
def open_cart():
    """Open Domino's cart in mini window."""
    phone = request.args.get("phone", "")
    user_id = get_user_from_request()

    if not user_id:
        return render_error("User not identified.")

    cookies = session_store.get_session_cookies(user_id, phone)
    if not cookies:
        return render_error(f"No session found for {phone}.")

    cookie_b64 = base64.b64encode(json.dumps(cookies).encode()).decode()
    return redirect(
        f"/proxy/?url=/postorder-ui/cart&cookie={cookie_b64}&phone={phone}"
    )


@app.route("/proxy/")
@app.route("/proxy/<path:subpath>")
def proxy(subpath=""):
    """
    Reverse proxy: fetches Domino's page with user's session cookies.
    Adjusts all links/forms to go through the proxy.
    """
    url_param = request.args.get("url", "")
    cookie_b64 = request.args.get("cookie", "")
    phone = request.args.get("phone", "")

    if not cookie_b64:
        return render_error("Missing session cookie.")

    try:
        cookies = json.loads(base64.b64decode(cookie_b64).decode())
    except Exception:
        return render_error("Invalid session cookie.")

    # Build the target URL
    target_path = url_param or f"/{subpath}"
    target_url = f"{DOMINOS_BASE_URL}{target_path}"

    # Forward query params (except our special ones)
    query_params = {k: v for k, v in request.args.items()
                    if k not in ("url", "cookie", "phone", "tg_id",
                                 "tgWebAppData", "tgWebAppVersion",
                                 "tgWebAppThemeColor", "tgWebAppPlatform")}

    # Make the request to Domino's with the saved cookies
    try:
        resp = requests.get(
            target_url,
            params=query_params if query_params else None,
            cookies={c["name"]: c["value"] for c in cookies},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.6422.147 Mobile Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,"
                          "application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
            },
            timeout=15,
        )
    except requests.RequestException as e:
        return render_error(f"Failed to reach Domino's: {e}")

    # Get the HTML content
    content = resp.text
    content_type = resp.headers.get("Content-Type", "text/html")

    # If it's HTML, rewrite links to go through our proxy
    if "text/html" in content_type:
        content = rewrite_html_links(
            content, DOMINOS_BASE_URL, cookie_b64, phone
        )
        # Inject our toolbar at the top
        content = inject_toolbar(content, phone)

    # Create Flask response
    flask_resp = Response(content, status=resp.status_code)
    flask_resp.headers["Content-Type"] = content_type

    # Don't cache
    flask_resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return flask_resp


def rewrite_html_links(html: str, base_url: str, cookie_b64: str, phone: str) -> str:
    """
    Rewrite all links so they go through our proxy.
    """

    def _rewrite(match):
        attr = match.group(1)  # href or src or action
        value = match.group(2)

        # Skip absolute external URLs, anchors, javascript, data URIs
        if value.startswith("http") and base_url not in value:
            return match.group(0)
        if value.startswith("#") or value.startswith("javascript:") \
                or value.startswith("data:"):
            return match.group(0)

        # Make absolute
        if value.startswith("/"):
            abs_url = value
        elif value.startswith("http"):
            abs_url = value.replace(base_url, "")
        else:
            abs_url = f"/{value}"

        # Rewrite to proxy URL
        new_url = f"/proxy/?url={abs_url}&cookie={cookie_b64}&phone={phone}"
        return f'{attr}="{new_url}"'

    # Rewrite href, src, action attributes
    html = re.sub(
        r'(href|src|action)="([^"]*)"',
        _rewrite,
        html,
    )

    # Rewrite form actions
    html = re.sub(
        r"action='([^']*)'",
        lambda m: f"action='/proxy/?url={m.group(1)}&cookie={cookie_b64}&phone={phone}'",
        html,
    )

    return html


def inject_toolbar(html: str, phone: str) -> str:
    """Inject a small toolbar at the top showing the account."""
    toolbar = f"""
    <!-- Domino's Bot Toolbar -->
    <div style="
        background: #006491;
        color: white;
        padding: 8px 12px;
        font-family: Arial, sans-serif;
        font-size: 13px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: sticky;
        top: 0;
        z-index: 9999;
    ">
        <span>🍕 Domino's | {phone}</span>
        <span style="font-size: 11px; color: #e3f2fd;">✓ Logged in</span>
    </div>
    """
    # Inject after <body> or at the beginning
    body_tag = "</head>"
    if body_tag in html:
        html = html.replace(body_tag, body_tag + toolbar)
    else:
        html = toolbar + html

    return html


def render_error(message: str) -> str:
    """Render an error page."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Domino's Bot</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 40px 20px;
                background: #f5f5f5;
            }}
            .error {{
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h2 {{ color: #d32f2f; }}
            p {{ color: #555; line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="error">
            <h2>❌ Error</h2>
            <p>{message}</p>
            <p style="margin-top:20px;font-size:12px;color:#999;">
                Telegram Bot से दोबारा प्रयास करें
            </p>
        </div>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    logger.info(f"🚀 Proxy server starting on {PROXY_HOST}:{PROXY_PORT}")
    app.run(host=PROXY_HOST, port=PROXY_PORT, debug=False)
