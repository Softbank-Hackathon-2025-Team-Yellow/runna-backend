from contextlib import asynccontextmanager
from typing import Optional

import redis

from app.config import settings


class RedisClient:
    _instance: Optional[redis.Redis] = None
    _pool: Optional[redis.ConnectionPool] = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            cls._initialize()
        return cls._instance

    @classmethod
    def _initialize(cls):
        cls._pool = redis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            # db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        cls._instance = redis.Redis(connection_pool=cls._pool)

    @classmethod
    def close(cls):
        if cls._instance:
            cls._instance.close()
            cls._instance = None
        if cls._pool:
            cls._pool.disconnect()
            cls._pool = None


def get_redis_client() -> redis.Redis:
    return RedisClient.get_instance()


@asynccontextmanager
async def get_redis_with_fallback():
    try:
        client = get_redis_client()
        yield client
    except redis.ConnectionError:
        yield None
    except Exception:
        yield None
