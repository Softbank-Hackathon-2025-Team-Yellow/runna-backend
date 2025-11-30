import json
import redis
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel

from app.core.redis import get_redis_client


class RedisService:
    def __init__(self):
        self.client = get_redis_client()
        self.key_prefix = "runna"

    def _build_key(self, namespace: str, identifier: str) -> str:
        return f"{self.key_prefix}:{namespace}:{identifier}"

    def _serialize(self, data: Any) -> str:
        if isinstance(data, BaseModel):
            return data.model_dump_json()
        return json.dumps(data, default=str)

    def _deserialize(self, data: str) -> Any:
        return json.loads(data)

    def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        try:
            redis_key = self._build_key(namespace, key)
            serialized_value = self._serialize(value)
            return self.client.set(redis_key, serialized_value, ex=ttl)
        except redis.ConnectionError:
            return False

    def get(self, namespace: str, key: str) -> Optional[Any]:
        try:
            redis_key = self._build_key(namespace, key)
            value = self.client.get(redis_key)
            if value is None:
                return None
            return self._deserialize(value)
        except redis.ConnectionError:
            return None
        except json.JSONDecodeError:
            return None

    def delete(self, namespace: str, key: str) -> bool:
        try:
            redis_key = self._build_key(namespace, key)
            return bool(self.client.delete(redis_key))
        except redis.ConnectionError:
            return False

    def exists(self, namespace: str, key: str) -> bool:
        try:
            redis_key = self._build_key(namespace, key)
            return bool(self.client.exists(redis_key))
        except redis.ConnectionError:
            return False

    def lpush(self, namespace: str, key: str, value: Any) -> bool:
        try:
            redis_key = self._build_key(namespace, key)
            serialized_value = self._serialize(value)
            self.client.lpush(redis_key, serialized_value)
            self.client.xadd(redis_key, serialized_value)
            return True
        except redis.ConnectionError:
            return False

    def rpop(self, namespace: str, key: str) -> Optional[Any]:
        try:
            redis_key = self._build_key(namespace, key)
            value = self.client.rpop(redis_key)
            if value is None:
                return None
            return self._deserialize(value)
        except redis.ConnectionError:
            return None
        except json.JSONDecodeError:
            return None

    def llen(self, namespace: str, key: str) -> int:
        try:
            redis_key = self._build_key(namespace, key)
            return self.client.llen(redis_key)
        except redis.ConnectionError:
            return 0

    def bulk_set(self, items: List[Dict[str, Any]], ttl: Optional[int] = None) -> bool:
        try:
            pipe = self.client.pipeline()
            for item in items:
                namespace = item.get("namespace")
                key = item.get("key")
                value = item.get("value")
                redis_key = self._build_key(namespace, key)
                serialized_value = self._serialize(value)
                pipe.set(redis_key, serialized_value, ex=ttl)
            pipe.execute()
            return True
        except redis.ConnectionError:
            return False

    def keys_by_pattern(self, pattern: str) -> List[str]:
        try:
            full_pattern = f"{self.key_prefix}:{pattern}"
            keys = self.client.keys(full_pattern)
            return [key.replace(f"{self.key_prefix}:", "") for key in keys]
        except redis.ConnectionError:
            return []
