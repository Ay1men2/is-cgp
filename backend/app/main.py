from fastapi import FastAPI
from sqlalchemy import text

from .deps import get_engine, get_redis

app = FastAPI(title="IS-CPG Backend", version="0.1.0")

from .api import router as v1_router
app.include_router(v1_router)

@app.get("/healthz")
def healthz():
    # DB check
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("select 1"))

    # Redis check
    r = get_redis()
    if r.ping() is not True:
        raise RuntimeError("redis ping failed")

    return {"status": "ok", "db": "ok", "redis": "ok"}

