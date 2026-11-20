"""Environment-backed application settings.

Keep configuration small and explicit while the project is in its first milestone.
"""

import os

APP_NAME = os.getenv("APP_NAME", "OpsPilot AI API")
APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./opspilot.db")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
