"""Development data initialization for easier testing and debugging."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import startup_log
from app.core.security import get_password_hash
from app.models.project import Project
from app.models.staff import Staff, StaffRole, StaffStatus

logger = logging.getLogger("app.core.dev_data")




def log_startup_banner() -> None:
    """Log beautiful startup banner."""
    startup_log("╔══════════════════════════════════════════════════════════════╗")
    startup_log("║                    🚀 TGO API Service                        ║")
    startup_log("║                  Core Business Logic Service                 ║")
    startup_log("╚══════════════════════════════════════════════════════════════╝")
    startup_log("")
    startup_log(f"📦 Version: {settings.PROJECT_VERSION}")
    startup_log(f"🌍 Environment: {settings.ENVIRONMENT.upper()}")
    startup_log("")
