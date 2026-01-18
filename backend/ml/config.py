"""
Configuration for ML pipeline.
Reads from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection (reuse existing app.db config)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# Support both MONGO_DB and legacy DB_NAME
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("DB_NAME") or "nba_pairs"

EVENTS_COLLECTION = os.getenv("EVENTS_COLLECTION", "events")

# Output directory
OUTPUT_DIR = Path(os.getenv("ML_OUTPUT_DIR", "backend/ml/artifacts"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Label field
# Support both LABEL_FIELD and ML_LABEL_FIELD
LABEL_FIELD = os.getenv("LABEL_FIELD") or os.getenv("ML_LABEL_FIELD") or "TEAM_TOTAL_OVER_HIT"

# Support both DATE_FIELD and ML_DATE_FIELD
DATE_FIELD_OVERRIDE = os.getenv("DATE_FIELD") or os.getenv("ML_DATE_FIELD")


# Field mappings (to handle variations in column names)
FIELD_MAPPINGS = {
    "game_id": ["GAME_ID", "game_id", "GAMEID"],
    "team_id": ["TEAM_ID", "team_id", "TEAMID"],
    "team_abbreviation": ["TEAM_ABBREVIATION", "team_abbreviation"],
    "date": ["GAME_DATE", "game_date", "DATE", "date", "start_time", "START_TIME"],
}

# Backtest configuration
# Task 4: Adjust for multiple folds (~979 rows -> MIN_TRAIN_SIZE=400, TEST_CHUNK_SIZE=100)
MIN_TRAIN_SIZE = int(os.getenv("ML_MIN_TRAIN_SIZE", "400"))
TEST_CHUNK_SIZE = int(os.getenv("ML_TEST_CHUNK_SIZE", "100"))

# Rolling window sizes
ROLLING_WINDOWS = [5, 10]  # Can expand if needed

# Model configuration
# Task 1: LogisticRegression C parameter (default 0.1 for stronger regularization)
LOGISTIC_C = float(os.getenv("ML_LOGISTIC_C", "0.1"))
LOGISTIC_MAX_ITER = int(os.getenv("ML_LOGISTIC_MAX_ITER", "2000"))
