from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from .deps import get_engine
from .schemas import ProjectCreate, ProjectOut, SessionCreate, SessionOut

router = APIRouter(prefix="/v1", tags=["v1"])

@router.get("/sessions")
def list_sessions():
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("select id, project_id, created_at from sessions order by created_at desc limit 50")
        ).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["project_id"] = str(d["project_id"])
        items.append(d)

    return {"items": items}


@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate):
    with get_engine().begin() as conn:
        # 唯一性简单处理：如果重名就报 409
        exists = conn.execute(
            text("select 1 from projects where name = :name"),
            {"name": payload.name},
        ).first()
        if exists:
            raise HTTPException(status_code=409, detail="project name already exists")

        row = conn.execute(
            text("insert into projects (name) values (:name) returning id, name"),
            {"name": payload.name},
        ).mappings().one()

    return row


@router.post("/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate):
    with get_engine().begin() as conn:
        # project 必须存在
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

    return row

