"""
Yetal Advertising Bot - Telegram Bot for Ethiopian Business Discovery
Version: 2.0.0
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests

# Telegram imports with compatibility check
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Bot, Update
    from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, Dispatcher
    from telegram.ext import MessageHandler, Filters
    from telegram.utils.helpers import escape_markdown
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please install required packages: pip install python-telegram-bot==13.7")
    sys.exit(1)

# ==================== CONFIGURATION ====================

load_dotenv()

class Config:
    """Application configuration"""
    VERSION = "2.0.0"
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7876492781:AAHtEw1M9RMphhV6GP8QlOF-vhTiNrARWOs")
    ADMIN_CODE = os.getenv("ADMIN_CODE")
    REGISTRATION_BOT_URL = os.getenv("REGISTRATION_BOT_URL", "https://t.me/YourRegistrationBot")
    CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "raniyaya71@gmail.com")
    WEBSITE_URL =  "https://yetal.co"
    
    # Server settings
    IS_PRODUCTION = os.getenv("RENDER_EXTERNAL_URL") is not None
    EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5000")
    PORT = int(os.environ.get("PORT", 5000))
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate and format URL"""
        if not url:
            return ""
        url = url.strip()
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("t.me/"):
            return f"https://{url}"
        return f"https://{url}"
    
    @classmethod
    def initialize(cls):
        """Initialize and validate configuration"""
        cls.REGISTRATION_BOT_URL = cls.validate_url(cls.REGISTRATION_BOT_URL)
        cls.WEBSITE_URL = cls.validate_url(cls.WEBSITE_URL)

Config.initialize()

# ==================== LOGGING SETUP ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================

app = Flask(__name__)

# Global bot instances
bot_instance: Optional[Bot] = None
dispatcher_instance: Optional[Dispatcher] = None
updater_instance: Optional[Updater] = None

# ==================== DECORATORS ====================

def handle_errors(func):
    """Decorator for error handling in callbacks"""
    @wraps(func)
    def wrapper(update: Update, context: Any):
        try:
            return func(update, context)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            if update and update.effective_message:
                update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
    return wrapper

# ==================== MESSAGE TEMPLATES ====================

class Messages:
    """Message templates"""
    
    WELCOME = """
👋 **ሰላም! ወደ የታል (Yetal) በደህና መጡ!**

የየዕለቱን ልዩ የሽልማት ዕድል እንዳያመልጥዎ!

🔥 **የዕለቱ የደንበኝነት ማስተዋወቂያ (Daily Subscription Promo)**
• በቀን ውስጥ ቀድመው ለሚመዘገቡ **25 ሰዎች** ልዩ ሽልማቶች ተዘጋጅተዋል።
• **1ኛ እና 2ኛ፡** የ 1,000 ብር የቸኮሌት እና ማስቲካ ስጦታ
• **3ኛ እስከ 5ኛ፡** የ 500 ብር የቸኮሌት ስጦታ
• **6ኛ እስከ 25ኛ፡** የተለያዩ ምርቶች ወይም ቫውቸሮች
• **ለሌሎች በሙሉ፡** የ 15% ቅናሽ ተዘጋጅቷል!

👇 **ከታች ያለውን ሊንክ ተጠቅመው በመግባት እድለኛ ይሁኑ!**
"""
    
    ABOUT = """
🔎 *About Yetal – Ethiopia's Digital Search Hub* 🔎

🌍 *Our Purpose*
Yetal was created to solve one problem:
*People struggle to find the right products and services online.*

🎯 *What We Do*
• Index shops, products & services  
• Help users search & compare  
• Promote businesses
• Connect buyers directly with sellers  

🏪 *Who Uses Yetal?*
• Customers searching for options  
• Shops wanting visibility  
• Service providers advertising locally  

🚀 *Our Vision*
To become Ethiopia's most trusted search and discovery platform.
"""
    
    @staticmethod
    def contact(email: str, website: str) -> str:
        return f"""
📞 **የመገናኛ መረጃ**

ለማንኛውም ጥያቄ በእነዚህ አድራሻዎች ያግኙን፡

📧 **ኢሜይል:** {email}
📱 **ስልክ:** +251910446666
💬 **ቴሌግራም:** @RaniyaKelifa
🌐 **ድረ-ገጽ:** {website}

የመረጡን እናመሰግናለን!
"""
    
    HELP = """
🆘 *Yetal Bot Help* 🆘

Available commands:
• /start - Welcome message and main menu
• /about - Learn about Yetal
• /contact - Contact information
• /help - Show this help message

*We're here 24/7 to assist you!* 🌙
"""

# ==================== KEYBOARD BUILDERS ====================

class Keyboards:
    """Keyboard builders"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Build main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("🚀 አሁኑኑ ይመዝገቡ (Subscribe/Buy)", 
                                  url=Config.WEBSITE_URL)],
            [InlineKeyboardButton("📞 ያግኙን (Contact Info)", 
                                  callback_data='contact')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button() -> InlineKeyboardMarkup:
        """Build back button keyboard"""
        keyboard = [[InlineKeyboardButton("🔙 ወደ መጀመሪያው ተመለስ", 
                                         callback_data='main_menu')]]
        return InlineKeyboardMarkup(keyboard)

# ==================== HANDLERS ====================

@handle_errors
def start(update: Update, context: Any) -> None:
    """Handle /start command"""
    update.message.reply_text(
        Messages.WELCOME,
        reply_markup=Keyboards.main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"User {update.effective_user.id} started the bot")

@handle_errors
def about(update: Update, context: Any) -> None:
    """Handle /about command"""
    update.message.reply_text(
        Messages.ABOUT,
        parse_mode=ParseMode.MARKDOWN
    )

@handle_errors
def contact(update: Update, context: Any) -> None:
    """Handle /contact command"""
    update.message.reply_text(
        Messages.contact(Config.CONTACT_EMAIL, Config.WEBSITE_URL),
        parse_mode=ParseMode.MARKDOWN
    )

@handle_errors
def help_command(update: Update, context: Any) -> None:
    """Handle /help command"""
    update.message.reply_text(
        Messages.HELP,
        parse_mode=ParseMode.MARKDOWN
    )

@handle_errors
def unknown(update: Update, context: Any) -> None:
    """Handle unknown commands"""
    update.message.reply_text(
        "❌ Sorry, I didn't understand that command.\n\n"
        "Try /start to begin or /help for available commands.",
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== CALLBACK HANDLERS ====================

@handle_errors
def callback_contact(update: Update, context: Any) -> None:
    """Handle contact callback"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        Messages.contact(Config.CONTACT_EMAIL, Config.WEBSITE_URL),
        reply_markup=Keyboards.back_button(),
        parse_mode=ParseMode.MARKDOWN
    )

@handle_errors
def callback_main_menu(update: Update, context: Any) -> None:
    """Return to main menu"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        Messages.WELCOME,
        reply_markup=Keyboards.main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== ERROR HANDLER ====================

def error_handler(update: Update, context: Any) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

# ==================== BOT SETUP ====================

def setup_bot() -> bool:
    """Initialize and configure the bot"""
    global bot_instance, dispatcher_instance, updater_instance
    
    try:
        # Create bot instance
        bot_instance = Bot(token=Config.BOT_TOKEN)
        updater_instance = Updater(bot=bot_instance, use_context=True)
        dispatcher_instance = updater_instance.dispatcher
        
        # Register command handlers
        dispatcher_instance.add_handler(CommandHandler("start", start))
        dispatcher_instance.add_handler(CommandHandler("about", about))
        dispatcher_instance.add_handler(CommandHandler("contact", contact))
        dispatcher_instance.add_handler(CommandHandler("help", help_command))
        
        # Register callback handlers
        dispatcher_instance.add_handler(CallbackQueryHandler(callback_contact, pattern='^contact$'))
        dispatcher_instance.add_handler(CallbackQueryHandler(callback_main_menu, pattern='^main_menu$'))
        
        # Register fallback handler
        dispatcher_instance.add_handler(MessageHandler(Filters.command, unknown))
        
        # Register error handler
        dispatcher_instance.add_error_handler(error_handler)
        
        # Configure webhook/polling
        if Config.IS_PRODUCTION:
            webhook_url = f"{Config.EXTERNAL_URL}/{Config.BOT_TOKEN}"
            bot_instance.delete_webhook()
            time.sleep(1)
            bot_instance.set_webhook(webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        else:
            bot_instance.delete_webhook()
            time.sleep(1)
            
            def start_polling():
                updater_instance.start_polling()
                logger.info("Bot is polling for updates")
            
            threading.Thread(target=start_polling, daemon=True).start()
        
        # Log bot info
        bot_info = bot_instance.get_me()
        logger.info(f"Bot @{bot_info.username} initialized successfully")
        logger.info(f"Mode: {'Webhook' if Config.IS_PRODUCTION else 'Polling'}")
        
        return True
        
    except Exception as e:
        logger.error(f"Bot setup failed: {e}")
        return False

# ==================== FLASK ROUTES ====================

@app.route('/')
def home():
    """Home page with status"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Yetal Bot</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                margin-top: 50px;
            }}
            h1 {{ color: #FFD700; text-align: center; }}
            .status {{
                background: rgba(0, 255, 0, 0.2);
                padding: 15px;
                border-radius: 10px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Yetal Advertising Bot</h1>
            <div class="status">
                ✅ <strong>BOT IS RUNNING</strong><br>
                Version: {Config.VERSION}<br>
                Mode: {'Webhook' if Config.IS_PRODUCTION else 'Polling'}
            </div>
            <p style="text-align: center;">📞 Contact: {Config.CONTACT_EMAIL}</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": Config.VERSION,
        "mode": "production" if Config.IS_PRODUCTION else "local"
    })

@app.route(f'/{Config.BOT_TOKEN}', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates"""
    if not Config.IS_PRODUCTION:
        return "Webhook not available in local mode", 400
    
    try:
        update_data = request.get_json()
        if update_data and dispatcher_instance:
            update = Update.de_json(update_data, bot_instance)
            dispatcher_instance.process_update(update)
            return 'ok', 200
        return 'no data', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'error', 500

# ==================== MAIN ====================

def main():
    """Main entry point"""
    print("=" * 60)
    print(f"🚀 Yetal Bot v{Config.VERSION}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Mode: {'PRODUCTION' if Config.IS_PRODUCTION else 'LOCAL'}")
    print("=" * 60)
    
    # Create .env file if not exists
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("""# Telegram Bot Token
BOT_TOKEN=7876492781:AAHtEw1M9RMphhV6GP8QlOF-vhTiNrARWOs

# URLs
CONTACT_EMAIL=raniyaya71@gmail.com
WEBSITE_URL=https://yetal.co

# For local development, comment out RENDER_EXTERNAL_URL
# RENDER_EXTERNAL_URL=http://localhost:5000
""")
        print("📝 Created sample .env file")
    
    # Setup bot
    if not setup_bot():
        logger.error("Failed to setup bot. Exiting.")
        sys.exit(1)
    
    # Start Flask server
    logger.info(f"Starting Flask server on port {Config.PORT}")
    
    if Config.IS_PRODUCTION:
        try:
            from waitress import serve
            serve(app, host="0.0.0.0", port=Config.PORT)
        except ImportError:
            app.run(host="0.0.0.0", port=Config.PORT, debug=False)
    else:
        app.run(host="0.0.0.0", port=Config.PORT, debug=True, use_reloader=False)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        if updater_instance:
            updater_instance.stop()
        sys.exit(0)