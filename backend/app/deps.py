from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
import redis

from .config import settings

_engine: Engine | None = None
_redis: redis.Redis | None = None

def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine

def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

