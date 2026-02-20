from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import UsageLog, User


async def check_and_increment_usage(
    user: User, db: AsyncSession
) -> tuple[bool, int, int]:
    """Check if user has remaining queries today and increment if allowed.

    Returns (allowed, used_count, daily_limit).
    """
    today = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(UsageLog).where(
            UsageLog.user_id == user.id,
            UsageLog.date == today,
        )
    )
    usage = result.scalar_one_or_none()

    if usage is None:
        usage = UsageLog(user_id=user.id, date=today, query_count=0)
        db.add(usage)
        await db.flush()

    if usage.query_count >= user.daily_query_limit:
        return False, usage.query_count, user.daily_query_limit

    usage.query_count += 1
    await db.flush()
    return True, usage.query_count, user.daily_query_limit


async def get_usage(user: User, db: AsyncSession) -> tuple[int, int]:
    """Get current usage count and limit."""
    today = datetime.now(timezone.utc).date()

    result = await db.execute(
        select(UsageLog).where(
            UsageLog.user_id == user.id,
            UsageLog.date == today,
        )
    )
    usage = result.scalar_one_or_none()
    used = usage.query_count if usage else 0
    return used, user.daily_query_limit
