from fastapi import APIRouter

# 旧 v1 API：你原来的 api.py 改名成 api_v1.py 后，这里作为 legacy router 挂进来
from app.api.v1 import router as v1_router

# 新增 RLM 子路由（要求 app/api/v1/rlm.py 内 prefix="/rlm"）


router = APIRouter(prefix="/v1", tags=["v1"])

router.include_router(v1_router)
