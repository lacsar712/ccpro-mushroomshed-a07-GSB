from datetime import timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy import func

from app.database import SessionLocal
from app.models.flush_harvest import FlushHarvest
from app.models.harvest_quota_day import HarvestQuotaDay
from app.models.room import Room
from app.schemas.flush_harvest import FlushHarvestCreateSchema, FlushHarvestOutSchema
from app.utils import cn_date_of, cn_day_bounds, validation_error_response

bp = Blueprint("flush_harvests", __name__, url_prefix="/api/flush-harvests")

create_schema = FlushHarvestCreateSchema()
out_schema = FlushHarvestOutSchema()
out_many = FlushHarvestOutSchema(many=True)


def _quota_missing(room_id: int, work_date, grade: str):
    return (
        jsonify(
            {
                "detail": f"{work_date.isoformat()} 该出菇室 {grade} 级未配置采收配额，按默认策略拒绝采收",
                "reason": "quota_missing",
                "roomId": room_id,
                "workDate": work_date.isoformat(),
                "grade": grade,
            }
        ),
        409,
    )


def _quota_exceeded(room_id: int, work_date, grade: str, cap_kg: float, used_kg: float, incoming_kg: float):
    return (
        jsonify(
            {
                "detail": (
                    f"超出 {work_date.isoformat()} {grade} 级采收配额："
                    f"当日累计 {round(used_kg, 3)}kg + 本次 {incoming_kg}kg > 上限 {cap_kg}kg"
                ),
                "reason": "quota_exceeded",
                "roomId": room_id,
                "workDate": work_date.isoformat(),
                "grade": grade,
                "capKg": cap_kg,
                "usedKg": round(used_kg, 3),
                "incomingKg": incoming_kg,
                "projectedKg": round(used_kg + incoming_kg, 3),
                "remainingKg": round(max(cap_kg - used_kg, 0.0), 3),
            }
        ),
        409,
    )


@bp.get("")
@jwt_required()
def list_flush_harvests():
    db = SessionLocal()
    try:
        room_id = request.args.get("roomId", type=int)
        q = db.query(FlushHarvest)
        if room_id is not None:
            q = q.filter(FlushHarvest.room_id == room_id)
        rows = q.order_by(FlushHarvest.harvested_at.desc()).all()
        return jsonify(out_many.dump(rows))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_flush_harvest():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        room = db.query(Room).filter(Room.id == data["room_id"]).first()
        if not room:
            return jsonify({"detail": "出菇室不存在"}), 400

        harvested_at = data["harvested_at"]
        if harvested_at.tzinfo is None:
            harvested_at = harvested_at.replace(tzinfo=timezone.utc)
        # 统一存 UTC 墙钟，避免不同时区写法混入后日切错位
        harvested_at = harvested_at.astimezone(timezone.utc)

        # 配额按 harvestedAt 的东八区自然日归属，绝不用 UTC 零点切日
        work_date = cn_date_of(harvested_at)
        grade = data["grade"]
        weight_kg = data["weight_kg"]

        # 行锁串行化同配额行的并发采收（MySQL 生效；SQLite 测试环境自动忽略）
        quota = (
            db.query(HarvestQuotaDay)
            .filter(
                HarvestQuotaDay.room_id == room.id,
                HarvestQuotaDay.work_date == work_date,
                HarvestQuotaDay.grade == grade,
            )
            .with_for_update()
            .first()
        )
        if quota is None:
            # 默认策略：无配额行即拒绝采收（不开放“无限采收”）
            return _quota_missing(room.id, work_date, grade)

        start_utc, end_utc = cn_day_bounds(work_date)
        used_kg = (
            db.query(func.coalesce(func.sum(FlushHarvest.weight_kg), 0.0))
            .filter(
                FlushHarvest.room_id == room.id,
                FlushHarvest.grade == grade,
                FlushHarvest.harvested_at >= start_utc,
                FlushHarvest.harvested_at < end_utc,
            )
            .scalar()
            or 0.0
        )

        if used_kg + weight_kg > quota.cap_kg + 1e-9:
            db.rollback()
            return _quota_exceeded(room.id, work_date, grade, quota.cap_kg, float(used_kg), weight_kg)

        item = FlushHarvest(
            room_id=room.id,
            harvested_at=harvested_at,
            flush_no=data["flush_no"],
            weight_kg=weight_kg,
            grade=grade,
            operator_name=data["operator_name"],
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return jsonify(out_schema.dump(item)), 201
    finally:
        db.close()


@bp.delete("/<int:harvest_id>")
@jwt_required()
def delete_flush_harvest(harvest_id: int):
    db = SessionLocal()
    try:
        item = db.query(FlushHarvest).filter(FlushHarvest.id == harvest_id).first()
        if not item:
            return jsonify({"detail": "采收记录不存在"}), 404
        db.delete(item)
        db.commit()
        return "", 204
    finally:
        db.close()
