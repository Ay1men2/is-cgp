# backend/app/deps.py
from functools import lru_cache
from sqlalchemy import create_engine
import redis

from app.config import settings

@lru_cache
def get_engine():
    return create_engine(settings.database_url, pool_pre_ping=True)

@lru_cache
def get_redis():
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
