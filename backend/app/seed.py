from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.database import SessionLocal
from app.models.climate_log import ClimateLog
from app.models.flush_harvest import FlushHarvest
from app.models.harvest_quota_day import HarvestQuotaDay
from app.models.room import Room
from app.models.shed import Shed
from app.models.user import User
from app.utils import cn_date_of


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(
                        username="admin",
                        hashed_password=hash_password("123456"),
                        role="admin",
                        display_name="场长",
                    ),
                    User(
                        username="fruiter",
                        hashed_password=hash_password("123456"),
                        role="fruiter",
                        display_name="出菇员",
                    ),
                ]
            )
            db.commit()

        if db.query(Shed).count() == 0:
            s1 = Shed(
                name="松木岭一号菇房",
                location="闽北高海拔林区 A 区",
                notes="主产香菇与平菇",
            )
            s2 = Shed(
                name="溪谷恒温菇房",
                location="山谷侧翼 B 区",
                notes="杏鲍菇与秀珍菇轮作",
            )
            db.add_all([s1, s2])
            db.flush()

            r1 = Room(
                shed_id=s1.id,
                room_code="R-01",
                species="香菇",
                capacity_bags=1200,
                status="fruiting",
            )
            r2 = Room(
                shed_id=s1.id,
                room_code="R-02",
                species="平菇",
                capacity_bags=800,
                status="idle",
            )
            r3 = Room(
                shed_id=s2.id,
                room_code="V-01",
                species="杏鲍菇",
                capacity_bags=600,
                status="fruiting",
            )
            r4 = Room(
                shed_id=s2.id,
                room_code="V-02",
                species="秀珍菇",
                capacity_bags=500,
                status="sanitize",
            )
            db.add_all([r1, r2, r3, r4])
            db.flush()

            now = datetime.now(timezone.utc)
            h1 = FlushHarvest(
                room_id=r1.id,
                harvested_at=now - timedelta(hours=6),
                flush_no=2,
                weight_kg=42.5,
                grade="A",
                operator_name="出菇员",
            )
            h2 = FlushHarvest(
                room_id=r1.id,
                harvested_at=now - timedelta(days=1),
                flush_no=1,
                weight_kg=38.0,
                grade="B",
                operator_name="场长",
            )
            h3 = FlushHarvest(
                room_id=r3.id,
                harvested_at=now - timedelta(days=3),
                flush_no=1,
                weight_kg=55.2,
                grade="A",
                operator_name="出菇员",
            )
            db.add_all(
                [
                    ClimateLog(
                        room_id=r1.id,
                        recorded_at=now - timedelta(hours=2),
                        temp_c=18.5,
                        humidity_pct=88,
                        co2_ppm=950.0,
                        notes="晨检正常",
                    ),
                    ClimateLog(
                        room_id=r1.id,
                        recorded_at=now - timedelta(hours=8),
                        temp_c=17.8,
                        humidity_pct=90,
                        co2_ppm=880.0,
                        notes=None,
                    ),
                    ClimateLog(
                        room_id=r3.id,
                        recorded_at=now - timedelta(hours=4),
                        temp_c=16.2,
                        humidity_pct=85,
                        co2_ppm=720.0,
                        notes="CO2 略偏高",
                    ),
                    ClimateLog(
                        room_id=r3.id,
                        recorded_at=now - timedelta(hours=12),
                        temp_c=15.9,
                        humidity_pct=87,
                        co2_ppm=690.0,
                        notes=None,
                    ),
                    h1,
                    h2,
                    h3,
                ]
            )
            db.flush()

            # 采收配额按 harvestedAt 的东八区自然日发放；至少覆盖 A/B 两级。
            # cap 略高于种子采收量，页面上可见已用/剩余；当日 A 级留出可继续录收的余量。
            today_cn = cn_date_of(now)
            quota_rows = [
                HarvestQuotaDay(
                    room_id=r1.id,
                    work_date=cn_date_of(h1.harvested_at),
                    grade="A",
                    cap_kg=80.0,
                ),
                HarvestQuotaDay(
                    room_id=r1.id,
                    work_date=cn_date_of(h2.harvested_at),
                    grade="B",
                    cap_kg=60.0,
                ),
                HarvestQuotaDay(
                    room_id=r3.id,
                    work_date=cn_date_of(h3.harvested_at),
                    grade="A",
                    cap_kg=70.0,
                ),
            ]
            # 今日（东八区自然日）若与历史采收不同日，补一条今日 A 级配额方便直接试录
            if today_cn not in {q.work_date for q in quota_rows if q.room_id == r1.id}:
                quota_rows.append(
                    HarvestQuotaDay(room_id=r1.id, work_date=today_cn, grade="A", cap_kg=50.0)
                )
            db.add_all(quota_rows)
            db.commit()
            print("Seed data inserted.")
        else:
            print("Seed skipped (data exists).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
