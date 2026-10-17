import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", ROOT / "artifacts"))
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "grievances.sqlite3"))
MODEL_PATH = ARTIFACT_DIR / "router.joblib"
DEFAULT_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.55"))
MIN_TEXT_CHARS = int(os.getenv("MIN_TEXT_CHARS", "20"))
OCR_MIN_CONFIDENCE = float(os.getenv("OCR_MIN_CONFIDENCE", "45"))
