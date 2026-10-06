import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = Path(os.environ.get("STORYROOM_DATA", ROOT / "data")).resolve()
FPS = 30
MAX_FILES = 30
MAX_SECONDS = 900
MAX_BYTES = 2_000_000_000
MODEL = os.getenv("STORYROOM_MODEL", "gemini-3.8-flash")
EMBED_MODEL = os.getenv("STORYROOM_EMBED_MODEL", "gemini-embedding-2")
INPUT_RATE = float(os.getenv("STORYROOM_INPUT_RATE", "1.50"))
OUTPUT_RATE = float(os.getenv("STORYROOM_OUTPUT_RATE", "9.00"))
EMBED_RATE = float(os.getenv("STORYROOM_EMBED_RATE", "0.20"))
SPEND_LIMIT = min(45.0, max(0.0, float(os.getenv("STORYROOM_SPEND_LIMIT", "45"))))
PRICING_CONFIRMED = os.getenv("STORYROOM_PRICING_CONFIRMED", "false").lower() == "true"
PROMPT_VERSION = "training-v1"


def ai_ready():
    return bool(os.getenv("GEMINI_API_KEY")) and PRICING_CONFIRMED


def asset_dir(asset_id):
    return DATA / "media" / asset_id
