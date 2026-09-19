from datetime import date, datetime, timedelta, timezone

from flask import jsonify
from marshmallow import ValidationError

# 采收配额的日切口径：东八区（UTC+8）自然日 00:00–24:00，不用 UTC 零点切日。
TZ_CN = timezone(timedelta(hours=8), name="UTC+8")


def validation_error_response(err: ValidationError):
    messages = []
    for field, msgs in err.messages.items():
        if isinstance(msgs, list):
            for m in msgs:
                messages.append(f"{field}: {m}" if field != "_schema" else str(m))
        else:
            messages.append(f"{field}: {msgs}")
    detail = "; ".join(messages) if messages else "请求参数校验失败"
    return jsonify({"detail": detail}), 400


def to_utc_naive(dt: datetime) -> datetime:
    """统一换算为 UTC 并去掉时区（库中时间列按 UTC 墙钟存储；naive 入参约定视为 UTC）。"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def work_date_of(harvested_at: datetime) -> date:
    """采收时间所属的东八区自然日：先换算到 UTC+8 再取日期。"""
    if harvested_at.tzinfo is None:
        harvested_at = harvested_at.replace(tzinfo=timezone.utc)
    return harvested_at.astimezone(TZ_CN).date()


def day_bounds_utc(work_date: date) -> tuple[datetime, datetime]:
    """东八区自然日 [00:00, 24:00) 对应的 UTC 区间（naive，与库中 UTC 墙钟直接比较）。"""
    start_cn = datetime(work_date.year, work_date.month, work_date.day, tzinfo=TZ_CN)
    end_cn = start_cn + timedelta(days=1)
    return (
        start_cn.astimezone(timezone.utc).replace(tzinfo=None),
        end_cn.astimezone(timezone.utc).replace(tzinfo=None),
    )
