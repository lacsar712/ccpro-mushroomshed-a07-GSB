from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.flush_harvest import FlushHarvest
from app.models.harvest_quota_day import HarvestQuotaDay
from app.models.room import Room
from app.schemas.harvest_quota_day import HarvestQuotaDayCreateSchema, HarvestQuotaDayOutSchema
from app.utils import day_bounds_utc, validation_error_response

bp = Blueprint("harvest_quota_days", __name__, url_prefix="/api/harvest-quota-days")

create_schema = HarvestQuotaDayCreateSchema()
out_schema = HarvestQuotaDayOutSchema()
out_many = HarvestQuotaDayOutSchema(many=True)


def _used_kg(db, room_id: int, work_date: date, grade: str) -> float:
    """该室该东八区自然日该等级已采累计（kg）。"""
    start_utc, end_utc = day_bounds_utc(work_date)
    return float(
        db.query(func.coalesce(func.sum(FlushHarvest.weight_kg), 0.0))
        .filter(
            FlushHarvest.room_id == room_id,
            FlushHarvest.grade == grade,
            FlushHarvest.harvested_at >= start_utc,
            FlushHarvest.harvested_at < end_utc,
        )
        .scalar()
    )


@bp.get("")
@jwt_required()
def list_harvest_quota_days():
    db = SessionLocal()
    try:
        q = db.query(HarvestQuotaDay)
        room_id = request.args.get("roomId", type=int)
        if room_id is not None:
            q = q.filter(HarvestQuotaDay.room_id == room_id)
        work_date_arg = request.args.get("workDate")
        if work_date_arg:
            try:
                work_date = date.fromisoformat(work_date_arg)
            except ValueError:
                return jsonify({"detail": "workDate 格式应为 YYYY-MM-DD"}), 400
            q = q.filter(HarvestQuotaDay.work_date == work_date)
        rows = q.order_by(
            HarvestQuotaDay.work_date.desc(),
            HarvestQuotaDay.room_id,
            HarvestQuotaDay.grade,
        ).all()
        data = out_many.dump(rows)
        for item, row in zip(data, rows):
            used = _used_kg(db, row.room_id, row.work_date, row.grade)
            item["usedKg"] = round(used, 3)
            item["remainingKg"] = round(row.cap_kg - used, 3)
        return jsonify(data)
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_harvest_quota_day():
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
            return jsonify({"detail": "该出菇室当日该等级配额已存在"}), 400
        db.refresh(item)
        return jsonify(out_schema.dump(item)), 201
    finally:
        db.close()


@bp.delete("/<int:quota_id>")
@jwt_required()
def delete_harvest_quota_day(quota_id: int):
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
