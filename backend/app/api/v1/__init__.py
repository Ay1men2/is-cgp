from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.deps import get_engine
from app.schemas import ProjectCreate, ProjectOut, SessionCreate, SessionOut

router = APIRouter(tags=["v1"])

from app.api.v1.rlm import router as rlm_router
router.include_router(rlm_router)





@router.get("/sessions")
def list_sessions():
    """
    返回最近 50 条 sessions
    """
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("select id, project_id, created_at from sessions order by created_at desc limit 50")
        ).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["project_id"] = str(d["project_id"])
        # created_at 让 FastAPI 自己序列化（datetime -> ISO string）
        items.append(d)

    return {"items": items}


@router.get("/projects", response_model=list[ProjectOut])
def list_projects():
    """
    方便调试：列出最近 50 个项目（避免每次进 DB 查 project_id）
    """
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("select id, name from projects order by created_at desc limit 50")
        ).mappings().all()

    items: list[dict] = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        items.append(d)

    return items


@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate):
    """
    幂等创建：
    - 同名已存在：直接返回已存在项目（200）
    - 不存在：创建并返回（200）
    """
    with get_engine().begin() as conn:
        existing = conn.execute(
            text("select id, name from projects where name = :name"),
            {"name": payload.name},
        ).mappings().first()

        if existing:
            d = dict(existing)
            d["id"] = str(d["id"])
            return d

        row = conn.execute(
            text("insert into projects (name) values (:name) returning id, name"),
            {"name": payload.name},
        ).mappings().one()

        d = dict(row)
        d["id"] = str(d["id"])
        return d


@router.post("/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate):
    """
    创建 session（project 必须存在）
    """
    with get_engine().begin() as conn:
        proj = conn.execute(
            text("select 1 from projects where id = :id"),
            {"id": str(payload.project_id)},
        ).first()
        if not proj:
            raise HTTPException(status_code=404, detail="project not found")

        row = conn.execute(
            text(
                "insert into sessions (project_id, created_by) "
                "values (:project_id, :created_by) "
                "returning id, project_id"
            ),
            {
                "project_id": str(payload.project_id),
                "created_by": (str(payload.created_by) if payload.created_by else None),
            },
        ).mappings().one()

        d = dict(row)
        d["id"] = str(d["id"])
        d["project_id"] = str(d["project_id"])
        return d


