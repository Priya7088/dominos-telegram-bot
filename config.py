import os

# === TELEGRAM BOT ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8521331381:AAFoCv9rGY6rodO2_yfNELVtsoE80Cp_ay8")

# === DOMINO'S INDIA ===
DOMINOS_BASE_URL = "https://www.dominos.co.in"
DOMINOS_MOBILE_URL = "https://m.dominos.co.in"
DOMINOS_API_GATEWAY = "https://api.dominos.co.in"

# === FLASK PROXY SERVER ===
PROXY_HOST = "0.0.0.0"
PROXY_PORT = int(os.getenv("PROXY_PORT", "8080"))
PROXY_PUBLIC_URL = os.getenv(
    "PROXY_PUBLIC_URL",
    "https://your-domain.com"  # Ngrok/Server URL डालें
)

# === BROWSER CONFIG ===
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "false"
PLAYWRIGHT_TIMEOUT = 30000  # 30 seconds

# Set to False for debugging - will show browser window
PLAYWRIGHT_HEADLESS = False  # CHANGE TO False FOR TESTING FIRST!

# === SESSION STORAGE ===
SESSION_DB_PATH = os.path.join(os.path.dirname(__file__), "sessions.json")

# === SECRET KEY ===
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-random-secret-key")
