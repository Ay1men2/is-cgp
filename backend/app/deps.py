# backend/app/deps.py
import os
from functools import lru_cache
from sqlalchemy import create_engine
import redis

@lru_cache
def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_engine(url, pool_pre_ping=True)

@lru_cache
def get_redis():
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.Redis.from_url(url, decode_responses=True)

