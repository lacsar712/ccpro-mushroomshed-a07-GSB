from datetime import date, datetime, time, timedelta, timezone
from flask import jsonify
from marshmallow import ValidationError

# 业务日切一律按东八区自然日，禁止用 UTC 零点切日。
CN_TZ = timezone(timedelta(hours=8))


def cn_date_of(value: datetime) -> date:
    """返回某时刻对应的东八区自然日日期。"""
    if value.tzinfo is None:
        # 兜底：naive 时间按 UTC 解释（marshmallow 收到带偏移的 ISO 串时通常已是 aware）
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CN_TZ).date()


def cn_day_bounds(work_date: date) -> tuple[datetime, datetime]:
    """东八区某自然日 [00:00, 次日 00:00) 对应的 UTC 半开区间。"""
    start_cn = datetime.combine(work_date, time.min, tzinfo=CN_TZ)
    end_cn = start_cn + timedelta(days=1)
    return start_cn.astimezone(timezone.utc), end_cn.astimezone(timezone.utc)


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
