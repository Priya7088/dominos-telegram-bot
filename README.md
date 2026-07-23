# 🍕 Domino's India Telegram Bot

एक पूर्ण Telegram Bot जो Domino's India पर ऑर्डर करने की सुविधा देता है।
OTP-based login, multi-account support, और Telegram WebApp mini window।

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 **New Login** | Domino's India पर OTP से लॉगिन करें |
| 👤 **My Account** | सभी सेव किए गए अकाउंट देखें और स्विच करें |
| 🛒 **Cart** | सीधे Domino's कार्ट में जाएँ |
| 🏠 **Home** | मुख्य मेनू |
| 📱 **Mini Window** | Telegram WebApp में Domino's की full website खोलें |
| 🔄 **Multi-Account** | एक साथ कई नंबरों से लॉगिन रखें |

## 🛠️ Installation

### Requirements
- Python 3.10+
- Node.js (Playwright के लिए)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/dominos-telegram-bot.git
cd dominos-telegram-bot

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers
playwright install chromium

# 4. Configure the bot
#    - BotFather से Telegram Bot Token लें
#    - config.py में BOT_TOKEN अपडेट करें
#    - या BOT_TOKEN environment variable सेट करें
export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

# 5. For the WebApp proxy, you need a public URL
#    (Use ngrok for testing)
ngrok http 8080
#    Copy the ngrok URL and set it:
export PROXY_PUBLIC_URL="https://your-ngrok-url.ngrok-free.app"
#    Also update in config.py

# 6. Run the bot
python bot.py

# 7. Run the proxy server (separate terminal)
python proxy_server.py
