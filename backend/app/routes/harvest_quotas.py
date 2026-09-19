from datetime import date, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.flush_harvest import FlushHarvest
from app.models.harvest_quota_day import HarvestQuotaDay
from app.models.room import Room
from app.schemas.harvest_quota_day import HarvestQuotaDayCreateSchema, HarvestQuotaDayOutSchema
from app.utils import CN_TZ, cn_day_bounds, validation_error_response

bp = Blueprint("harvest_quotas", __name__, url_prefix="/api/harvest-quotas")

create_schema = HarvestQuotaDayCreateSchema()
out_schema = HarvestQuotaDayOutSchema()


def _dump_quota(row: HarvestQuotaDay, used_map: dict) -> dict:
    payload = out_schema.dump(row)
    used = used_map.get((row.room_id, row.work_date, row.grade), 0.0)
    payload["usedKg"] = round(float(used), 3)
    payload["remainingKg"] = round(max(row.cap_kg - float(used), 0.0), 3)
    return payload


@bp.get("")
@jwt_required()
def list_quotas():
    db = SessionLocal()
    try:
        room_id = request.args.get("roomId", type=int)
        work_date_raw = request.args.get("workDate", type=str)
        work_date = None
        if work_date_raw:
            try:
                work_date = date.fromisoformat(work_date_raw)
            except ValueError:
                return jsonify({"detail": "workDate 须为 YYYY-MM-DD"}), 400
        q = db.query(HarvestQuotaDay)
        if room_id is not None:
            q = q.filter(HarvestQuotaDay.room_id == room_id)
        if work_date:
            q = q.filter(HarvestQuotaDay.work_date == work_date)
        rows = q.order_by(
            HarvestQuotaDay.work_date.desc(), HarvestQuotaDay.room_id, HarvestQuotaDay.grade
        ).all()

        # 已用量按每条采收 harvestedAt 实际所属东八区自然日归桶（绝不用 UTC 零点切日）
        used_map: dict = {}
        if rows:
            dates = sorted({r.work_date for r in rows})
            room_ids = {r.room_id for r in rows}
            start_utc, _ = cn_day_bounds(dates[0])
            _, end_utc = cn_day_bounds(dates[-1])
            harvests = (
                db.query(FlushHarvest)
                .filter(
                    FlushHarvest.room_id.in_(room_ids),
                    FlushHarvest.harvested_at >= start_utc,
                    FlushHarvest.harvested_at < end_utc,
                )
                .all()
            )
            for h in harvests:
                dt = h.harvested_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                key = (h.room_id, dt.astimezone(CN_TZ).date(), h.grade)
                used_map[key] = used_map.get(key, 0.0) + h.weight_kg

        return jsonify([_dump_quota(r, used_map) for r in rows])
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_quota():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        room = db.query(Room).filter(Room.id == data["room_id"]).first()
        if not room:
            return jsonify({"detail": "出菇室不存在"}), 400
        item = HarvestQuotaDay(
            room_id=data["room_id"],
            work_date=data["work_date"],
            grade=data["grade"],
            cap_kg=data["cap_kg"],
        )
        db.add(item)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return (
                jsonify(
                    {
                        "detail": (
                            f"{data['work_date'].isoformat()} 该出菇室 {data['grade']} 级配额已存在，"
                            "同室同日同等级只能有一条配额"
                        )
                    }
                ),
                409,
            )
        db.refresh(item)
        return jsonify(_dump_quota(item, {})), 201
    finally:
        db.close()


@bp.delete("/<int:quota_id>")
@jwt_required()
def delete_quota(quota_id: int):
    db = SessionLocal()
    try:
        item = db.query(HarvestQuotaDay).filter(HarvestQuotaDay.id == quota_id).first()
        if not item:
            return jsonify({"detail": "配额不存在"}), 404
        db.delete(item)
        db.commit()
        return "", 204
    finally:
        db.close()
