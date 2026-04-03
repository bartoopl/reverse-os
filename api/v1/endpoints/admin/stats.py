"""Admin dashboard stats."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.models.return_model import Return
from core.security.rbac import require_min_role

router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


@router.get("/", dependencies=[Depends(require_min_role("warehouse"))])
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    # Total returns by status
    status_rows = await db.execute(
        select(Return.status, func.count().label("n"))
        .group_by(Return.status)
    )
    by_status = {row.status: row.n for row in status_rows}

    # Returns today
    today_count = await db.execute(
        select(func.count()).where(
            func.date(Return.created_at) == func.current_date()
        )
    )

    # Returns last 30 days (daily breakdown)
    trend_rows = await db.execute(text("""
        SELECT date_trunc('day', created_at)::date AS day, COUNT(*) AS n
        FROM returns
        WHERE created_at >= NOW() - INTERVAL '30 days'
        GROUP BY 1
        ORDER BY 1
    """))
    trend = [{"date": str(row.day), "count": row.n} for row in trend_rows]

    # Avg approved refund
    avg_refund = await db.execute(
        select(func.avg(Return.approved_refund_amount))
        .where(Return.approved_refund_amount.isnot(None))
    )

    # Auto-approval rate
    auto = by_status.get("approved", 0) + by_status.get("keep_it", 0)
    total = sum(by_status.values()) or 1
    auto_rate = round(auto / total * 100, 1)

    # Returns needing action (warehouse queue)
    queue_count = await db.execute(
        select(func.count()).where(Return.status == "received")
    )

    return {
        "total": total,
        "today": today_count.scalar() or 0,
        "by_status": by_status,
        "trend_30d": trend,
        "avg_refund_pln": round(float(avg_refund.scalar() or 0), 2),
        "auto_approval_rate_pct": auto_rate,
        "warehouse_queue": queue_count.scalar() or 0,
    }
