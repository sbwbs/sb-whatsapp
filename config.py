import os
from dotenv import load_dotenv
import logging

load_dotenv()

class Config:
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_VERSION = os.getenv("WHATSAPP_VERSION", "v20.0")
    WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    SENDBIRD_API_URL = os.getenv("SENDBIRD_API_URL")
    SENDBIRD_API_TOKEN = os.getenv("SENDBIRD_API_TOKEN")
    BOT_USER_ID = os.getenv("BOT_USER_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[logging.StreamHandler()]
        )

