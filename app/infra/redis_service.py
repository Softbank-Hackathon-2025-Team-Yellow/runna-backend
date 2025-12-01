import json
from typing import Any, Dict, List, Optional, Union

import redis
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

    def xadd(
        self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None
    ) -> Optional[str]:
        try:
            stream_key = self._build_key("stream", stream)
            print(stream_key)
            serialized_fields = {}
            for key, value in fields.items():
                if isinstance(value, (dict, list)):
                    serialized_fields[key] = self._serialize(value)
                else:
                    serialized_fields[key] = str(value)

            kwargs = {}
            if maxlen is not None:
                kwargs["maxlen"] = maxlen
                kwargs["approximate"] = True

            return self.client.xadd(stream_key, serialized_fields, **kwargs)
        except redis.ConnectionError:
            return None

    def xgroup_create(
        self, stream: str, group_name: str, id: str = "0", mkstream: bool = True
    ) -> bool:
        try:
            stream_key = self._build_key("stream", stream)
            self.client.xgroup_create(stream_key, group_name, id=id, mkstream=mkstream)
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                return True
            return False
        except redis.ConnectionError:
            return False

    def xreadgroup(
        self,
        group_name: str,
        consumer_name: str,
        streams: Dict[str, str],
        count: Optional[int] = None,
        block: Optional[int] = None,
    ) -> List:
        try:
            stream_keys = {
                self._build_key("stream", stream): stream_id
                for stream, stream_id in streams.items()
            }

            kwargs = {}
            if count is not None:
                kwargs["count"] = count
            if block is not None:
                kwargs["block"] = block

            result = self.client.xreadgroup(
                group_name, consumer_name, stream_keys, **kwargs
            )

            processed_result = []
            for stream_key, messages in result:
                original_stream = stream_key.replace(f"{self.key_prefix}:stream:", "")
                processed_messages = []
                for msg_id, fields in messages:
                    processed_fields = {}
                    for key, value in fields.items():
                        try:
                            processed_fields[key] = self._deserialize(value)
                        except json.JSONDecodeError:
                            processed_fields[key] = value
                    processed_messages.append((msg_id, processed_fields))
                processed_result.append((original_stream, processed_messages))

            return processed_result
        except redis.ConnectionError:
            return []

    def xack(
        self, stream: str, group_name: str, message_ids: Union[str, List[str]]
    ) -> int:
        try:
            stream_key = self._build_key("stream", stream)
            if isinstance(message_ids, str):
                message_ids = [message_ids]
            return self.client.xack(stream_key, group_name, *message_ids)
        except redis.ConnectionError:
            return 0

    def publish(self, channel: str, message: Any) -> int:
        try:
            channel_key = self._build_key("channel", channel)
            serialized_message = self._serialize(message)
            return self.client.publish(channel_key, serialized_message)
        except redis.ConnectionError:
            return 0

    def get_pubsub(self):
        try:
            return self.client.pubsub()
        except redis.ConnectionError:
            return None

    def subscribe_channel(self, pubsub, channel: str) -> bool:
        try:
            channel_key = self._build_key("channel", channel)
            pubsub.subscribe(channel_key)
            return True
        except redis.ConnectionError:
            return False
