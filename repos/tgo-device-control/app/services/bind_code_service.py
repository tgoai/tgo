"""Redis-based bind code service."""

import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import redis.asyncio as redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("services.bind_code_service")


class BindCodeService:
    """Service for managing device bind codes in Redis."""

    KEY_PREFIX = "dc:bind_code:"
    ATTEMPT_PREFIX = "dc:bind_attempts:"
    MAX_ATTEMPTS = 5
    ATTEMPT_WINDOW = 3600  # 1 hour

    def __init__(self):
        logger.info(f"[DEBUG] BindCodeService initializing with REDIS_URL: {settings.REDIS_URL}")
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info(f"[DEBUG] BindCodeService Redis client created")

    def _generate_code(self) -> str:
        """Generate a random alphanumeric code."""
        return "".join(
            random.choices(
                string.ascii_uppercase + string.digits, k=settings.BIND_CODE_LENGTH
            )
        )

    async def generate(self, project_id: uuid.UUID) -> Tuple[str, datetime]:
        """
        Generate a unique bind code and store it in Redis.
        Returns the code and its expiration time.
        """
        logger.info(f"[DEBUG] Generating bind code for project {project_id}")
        logger.info(f"[DEBUG] Redis URL: {settings.REDIS_URL}")
        
        for attempt in range(5):  # Retry up to 5 times if code exists
            code = self._generate_code()
            key = f"{self.KEY_PREFIX}{code}"
            logger.info(f"[DEBUG] Attempt {attempt + 1}: Generated code {code}, key={key}")

            try:
                # SETNX to ensure uniqueness across all projects
                success = await self.redis.setnx(key, str(project_id))
                logger.info(f"[DEBUG] SETNX result for {key}: {success}")
                
                if success:
                    # Set expiration
                    expiry_seconds = settings.BIND_CODE_EXPIRY_MINUTES * 60
                    await self.redis.expire(key, expiry_seconds)
                    logger.info(f"[DEBUG] Set expiry {expiry_seconds}s for key {key}")

                    expires_at = datetime.now(timezone.utc) + timedelta(
                        minutes=settings.BIND_CODE_EXPIRY_MINUTES
                    )
                    logger.info(f"[DEBUG] Generated bind code {code} for project {project_id}, expires_at={expires_at}")
                    return code, expires_at
            except Exception as e:
                logger.error(f"[DEBUG] Redis error during bind code generation: {e}", exc_info=True)
                raise

        logger.error("[DEBUG] Failed to generate a unique bind code after 5 attempts")
        raise Exception("Failed to generate unique bind code")

    async def validate(self, code: str) -> Optional[uuid.UUID]:
        """
        Validate a bind code and return the associated project_id.
        The code is deleted after successful validation.
        """
        logger.info(f"[DEBUG] Validating bind code: {code}")
        # 1. Check rate limiting/attempts
        # Note: In a real production app, we'd use IP-based rate limiting
        # For now, we'll just implement basic validation

        key = f"{self.KEY_PREFIX}{code.upper()}"
        logger.info(f"[DEBUG] Looking up Redis key: {key}")
        
        try:
            project_id_str = await self.redis.get(key)
            logger.info(f"[DEBUG] Redis get result for {key}: {project_id_str}")
        except Exception as e:
            logger.error(f"[DEBUG] Redis error while getting key {key}: {e}", exc_info=True)
            return None

        if not project_id_str:
            logger.warning(f"[DEBUG] Invalid or expired bind code attempt: {code} (key not found in Redis)")
            # List all bind code keys for debugging
            try:
                all_keys = await self.redis.keys(f"{self.KEY_PREFIX}*")
                logger.info(f"[DEBUG] Existing bind code keys in Redis: {all_keys}")
            except Exception as e:
                logger.warning(f"[DEBUG] Could not list Redis keys: {e}")
            return None

        # 2. Success - delete the code (one-time use)
        logger.info(f"[DEBUG] Bind code valid, deleting key {key}")
        await self.redis.delete(key)

        try:
            result = uuid.UUID(project_id_str)
            logger.info(f"[DEBUG] Bind code validated successfully, project_id={result}")
            return result
        except ValueError:
            logger.error(f"[DEBUG] Invalid UUID stored in Redis for code {code}: {project_id_str}")
            return None

    async def check_rate_limit(self, identifier: str) -> bool:
        """
        Basic rate limiting for bind code attempts.
        Returns True if allowed, False if rate limited.
        """
        key = f"{self.ATTEMPT_PREFIX}{identifier}"
        attempts = await self.redis.get(key)

        if attempts and int(attempts) >= self.MAX_ATTEMPTS:
            return False

        return True

    async def record_attempt(self, identifier: str):
        """Record a failed bind code attempt."""
        key = f"{self.ATTEMPT_PREFIX}{identifier}"
        await self.redis.incr(key)
        await self.redis.expire(key, self.ATTEMPT_WINDOW)


# Global singleton instance
bind_code_service = BindCodeService()
