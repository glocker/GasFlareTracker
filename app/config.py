import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")
