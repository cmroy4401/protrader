import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

if not ACCESS_TOKEN:
    logger.error("❌ UPSTOX_ACCESS_TOKEN .env file mein nahi mila!")
else:
    logger.info("✅ Upstox Analytics Access Token successfully load ho gaya hai.")
