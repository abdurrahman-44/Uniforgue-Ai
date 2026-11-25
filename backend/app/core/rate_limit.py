"""Rate limiting (Redis-backed sliding window with automatic local fallback) & fair-use quotas."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import FairUseLimitError
from app.models.entities import UsageRecord

logger = logging.getLogger("uniforge.rate_limit")


class SlidingWindowRateLimiter:
    """Sliding-window rate limiter supporting Redis in multi-node prod with seamless local fallback."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._redis = None
        self._redis_checked = False

    def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        if settings.app_env == "test" or not settings.redis_url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.3, socket_timeout=0.3)
            client.ping()
            self._redis = client
            logger.info("rate_limiter_backend=redis")
        except Exception:
            self._redis = None
            logger.info("rate_limiter_backend=in_memory (redis unavailable)")
        return self._redis

    def check(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        r = self._get_redis()
        if r is not None:
            try:
                now = time.time()
                rkey = f"uniforge:rl:{key}"
                pipe = r.pipeline()
                pipe.zremrangebyscore(rkey, 0, now - window_seconds)
                pipe.zcard(rkey)
                pipe.zadd(rkey, {f"{now}:{time.monotonic_ns()}": now})
                pipe.expire(rkey, window_seconds + 5)
                _, current_count, _, _ = pipe.execute()
                if int(current_count) >= limit:
                    return False, max(1, window_seconds // 2)
                return True, 0
            except Exception:
                # Fall back to local limiter if Redis drops mid-flight
                self._redis = None

        now = time.monotonic()
        bucket = self._buckets[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            return False, retry_after
        bucket.append(now)
        return True, 0

    def reset(self) -> None:
        self._buckets.clear()
        self._redis = None
        self._redis_checked = False


rate_limiter = SlidingWindowRateLimiter()


FAIR_USE_LIMITS: dict[str, int] = {
    "ai_generation": settings.fair_use_ai_requests_per_day,
    "image_generation": settings.fair_use_images_per_day,
    "video_generation": settings.fair_use_videos_per_day,
    "document_export": settings.fair_use_exports_per_day,
}


async def enforce_fair_use(
    db: AsyncSession,
    user_id: str,
    category: str,
    user_role: str = "student",
) -> dict:
    """Check daily fair-use quota for a given category; admins get elevated capacity."""
    base_limit = FAIR_USE_LIMITS.get(category, 100)
    limit = base_limit * 10 if user_role == "admin" else base_limit

    since = datetime.now(timezone.utc) - timedelta(days=1)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.user_id == user_id,
            UsageRecord.resource_type == category,
            UsageRecord.created_at >= since,
        )
    )
    used = int(result.scalar() or 0)
    if used >= limit:
        raise FairUseLimitError(
            message=f"Daily fair-use limit reached for {category.replace('_', ' ')} ({used}/{limit}). "
            "UNIFORGE AI is free for all students; fair-use quotas reset every 24 hours.",
            details={"category": category, "used": used, "limit": limit, "window_hours": 24},
        )
    return {"category": category, "used": used, "limit": limit, "remaining": limit - used}


async def record_usage(
    db: AsyncSession,
    user_id: str,
    resource_type: str,
    quantity: int = 1,
    provider: str | None = None,
    model_name: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    metadata: dict | None = None,
) -> UsageRecord:
    rec = UsageRecord(
        user_id=user_id,
        resource_type=resource_type,
        quantity=quantity,
        provider=provider,
        model_name=model_name,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        extra_metadata=metadata or {},
    )
    db.add(rec)
    await db.flush()
    return rec
