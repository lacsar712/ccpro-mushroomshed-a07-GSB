# MushroomShed-01 · 菇房出菇台账

食用菌菇房「出菇室环境记录与采收台账」种子项目（非库存 / 电商 / 医院 / 考勤）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11 · Flask · SQLAlchemy 2 · Marshmallow · Flask-JWT-Extended · passlib(bcrypt) · gunicorn |
| 前端 | SolidJS · Vite · TypeScript · @solidjs/router |
| 数据库 | MySQL 8（协议兼容原 MariaDB 设计） |
| 部署 | docker-compose · 前端 Nginx 反代 `/api` |

## 端口与账号

| 服务 | 端口 |
| --- | --- |
| 前端 | **3800** |
| 后端 API | **8800** |
| MySQL | **3310** |

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | admin（场长） |
| `fruiter` | `123456` | fruiter（出菇员） |

数据库：`mushroomshed` / `mushroomshed`，库名 `mushroomshed`。JWT 密钥环境变量 **`JWT_SECRET`**。

## 一键启动

```bash
cd MushroomShed-01
docker compose up --build
```

启动后访问：

- 前端：http://localhost:3800
- 后端健康检查：http://localhost:8800/api/health

后端 entrypoint 流程：等待 MySQL 就绪 → `create_all` 建表 → seed 初始数据 → 启动 gunicorn。

## 功能模块

1. **Auth**：JWT 登录（OAuth2 表单或 JSON），`/api/auth/login`、`/api/auth/me`，`Authorization: Bearer`
2. **Shed 菇房**：`name`、`location`、`notes`
3. **Room 出菇室**：`shedId`、`roomCode`、`species`、`capacityBags`、`status(fruiting|idle|sanitize)`；同菇房 `roomCode` 唯一
4. **ClimateLog 环境记录**：`roomId`、`recordedAt`、`tempC`、`humidityPct`、`co2Ppm`、`notes`；`humidityPct ∈ [1,100]`，否则 **400**
5. **FlushHarvest 采收**：`roomId`、`harvestedAt`、`flushNo(≥1)`、`weightKg`、`grade(A|B|C)`、`operatorName`；`weightKg > 0`，否则 **400**
6. **HarvestQuotaDay 采收配额**：`roomId`、`workDate`（东八区自然日）、`grade(A|B|C)`、`capKg(>0)`；同室同日同等级唯一（重复 **400**）
7. **Dashboard**：`shedTotal`、`fruitingRoomCount`、`climateLast24h`、`harvestKgLast7d`

各实体 API：`GET/POST` 列表与创建、`DELETE` 按 ID 删除。配额接口为 `/api/harvest-quota-days`，列表回显 `usedKg` / `remainingKg`。

## 采收配额规则与日切口径

- **日切口径：东八区（UTC+8）自然日 00:00–24:00**。服务端把 `harvestedAt` 统一换算到 UTC+8 取日期作为 `workDate`；累计窗口即该自然日对应的 UTC 区间 `[前一日 16:00, 当日 16:00)`。**不使用 UTC 零点切日**（UTC 零点会把东八区当天 08:00 前的采收算进"昨天"，掏空当日额度）。库中时间列按 UTC 墙钟存储。
- 新建 FlushHarvest 时，按 `harvestedAt` 的东八区自然日与 `grade` 累加当日 `weightKg`：**当日累计 + 本次 > capKg** 则返回 **409**，响应体回显当日累计（`usedKg`、`capKg`、`attemptKg`）。
- **默认策略：无配额行即拒绝**。该室该东八区自然日该等级没有 HarvestQuotaDay 行时，采收返回 **409**，不放行、不兜底。需要采收必须先在「采收配额」页建对应配额行。

## 前端页面

Login · Dashboard · Sheds · Rooms · ClimateLogs · FlushHarvests · HarvestQuotas 采收配额（侧边栏布局；Rooms 行内「配额」可带 `roomId` 跳入）

## 本地开发（可选）

```bash
# 数据库（或用 compose 只起 db）
docker compose up -d db

# 后端
cd backend
pip install -r requirements.txt
set DATABASE_URL=mysql+pymysql://mushroomshed:mushroomshed@localhost:3310/mushroomshed
set JWT_SECRET=local-dev-secret
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
gunicorn wsgi:app --bind 0.0.0.0:8800 --reload

# 前端
cd frontend
npm install
npm run dev
```

## 目录结构

```
MushroomShed-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── wsgi.py
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       ├── seed.py
│       ├── utils.py
│       ├── models/
│       ├── schemas/
│       └── routes/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── pages/
        ├── components/
        └── api/
```
