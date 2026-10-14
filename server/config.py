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
EMBED_PROVIDER = os.getenv("STORYROOM_EMBED_PROVIDER", "gemini").strip().lower()
EMBED_DIMENSIONS = 768
VISUAL_INDEX_VERSION = "visual-v1-6s-3s-1fps"
VISUAL_WINDOW_FRAMES = 6 * FPS
VISUAL_STRIDE_FRAMES = 3 * FPS
VISUAL_VIDEO_FRAME_RATE = float(
    os.getenv("STORYROOM_VIDEO_EMBED_FRAME_RATE", "0.00079")
)
VISUAL_TIER = os.getenv("STORYROOM_GEMINI_TIER", "unpaid").strip().lower()
if VISUAL_TIER not in ("unpaid", "paid"):
    raise ValueError("STORYROOM_GEMINI_TIER must be 'unpaid' or 'paid'.")
UNPAID_TERMS_ACKNOWLEDGED = (
    os.getenv("STORYROOM_GEMINI_UNPAID_TERMS_ACKNOWLEDGED", "false").lower()
    == "true"
)
SPEND_LIMIT = min(45.0, max(0.0, float(os.getenv("STORYROOM_SPEND_LIMIT", "45"))))
PRICING_CONFIRMED = os.getenv("STORYROOM_PRICING_CONFIRMED", "false").lower() == "true"
PROMPT_VERSION = "training-v1"


def ai_ready():
    return bool(os.getenv("GEMINI_API_KEY")) and PRICING_CONFIRMED


def visual_ai_ready():
    if not os.getenv("GEMINI_API_KEY"):
        return False
    if VISUAL_TIER == "unpaid":
        return UNPAID_TERMS_ACKNOWLEDGED
    return VISUAL_TIER == "paid" and PRICING_CONFIRMED


def asset_dir(asset_id):
    return DATA / "media" / asset_id
