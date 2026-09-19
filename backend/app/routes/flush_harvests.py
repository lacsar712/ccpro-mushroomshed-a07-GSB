from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy import func

from app.database import SessionLocal
from app.models.flush_harvest import FlushHarvest
from app.models.harvest_quota_day import HarvestQuotaDay
from app.models.room import Room
from app.schemas.flush_harvest import FlushHarvestCreateSchema, FlushHarvestOutSchema
from app.utils import day_bounds_utc, to_utc_naive, validation_error_response, work_date_of

bp = Blueprint("flush_harvests", __name__, url_prefix="/api/flush-harvests")

create_schema = FlushHarvestCreateSchema()
out_schema = FlushHarvestOutSchema()
out_many = FlushHarvestOutSchema(many=True)


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

        # 统一按 UTC 存储，再按东八区自然日定位配额与累计窗口
        harvested_at = to_utc_naive(data["harvested_at"])
        work_date = work_date_of(harvested_at)
        grade = data["grade"]

        # 行锁串行化同室同日同等级的并发采收，防止累计超限竞态
        quota = (
            db.query(HarvestQuotaDay)
            .filter(
                HarvestQuotaDay.room_id == data["room_id"],
                HarvestQuotaDay.work_date == work_date,
                HarvestQuotaDay.grade == grade,
            )
            .with_for_update()
            .first()
        )
        if not quota:
            # 默认策略：无配额行即拒绝采收（见 README）
            return (
                jsonify(
                    {
                        "detail": f"{work_date.isoformat()}（东八区）{grade} 级未设置采收配额，已拒绝",
                        "roomId": data["room_id"],
                        "workDate": work_date.isoformat(),
                        "grade": grade,
                    }
                ),
                409,
            )

        start_utc, end_utc = day_bounds_utc(work_date)
        used_kg = float(
            db.query(func.coalesce(func.sum(FlushHarvest.weight_kg), 0.0))
            .filter(
                FlushHarvest.room_id == data["room_id"],
                FlushHarvest.grade == grade,
                FlushHarvest.harvested_at >= start_utc,
                FlushHarvest.harvested_at < end_utc,
            )
            .scalar()
        )
        weight_kg = data["weight_kg"]
        if used_kg + weight_kg > quota.cap_kg + 1e-9:
            return (
                jsonify(
                    {
                        "detail": (
                            f"超出当日采收配额：{work_date.isoformat()}（东八区）{grade} 级 "
                            f"已采 {round(used_kg, 3)}kg / 上限 {quota.cap_kg}kg，本次 {weight_kg}kg"
                        ),
                        "roomId": data["room_id"],
                        "workDate": work_date.isoformat(),
                        "grade": grade,
                        "capKg": quota.cap_kg,
                        "usedKg": round(used_kg, 3),
                        "attemptKg": weight_kg,
                    }
                ),
                409,
            )

        item = FlushHarvest(
            room_id=data["room_id"],
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
