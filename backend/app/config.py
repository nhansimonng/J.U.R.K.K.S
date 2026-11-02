import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
USDA_API_KEY = os.getenv("USDA_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
REVIEW_PHOTO_BUCKET = os.getenv("REVIEW_PHOTO_BUCKET", "review-photos")
CORS_ORIGINS = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(",") if origin.strip()]
