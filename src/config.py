import os
import sys

import pytz
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
DATA_DIR: str = os.getenv("DATA_DIR", "./data")
TIMEZONE = pytz.timezone("Asia/Bangkok")
CURRENCY: str = os.getenv("CURRENCY_SYMBOL", "฿")

DB_PATH = os.path.join(DATA_DIR, "finance.db")

_missing = [k for k, v in {"TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN, "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID}.items() if not v]
if _missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(_missing)}")
    sys.exit(1)


def is_authorized(chat_id: int) -> bool:
    return str(chat_id) == TELEGRAM_CHAT_ID
