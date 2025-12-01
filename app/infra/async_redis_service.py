"""
Async Redis Service using redis.asyncio for thread-safe operations
Provides async alternatives to synchronous Redis operations
"""

import json
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis
from pydantic import BaseModel

from app.config import settings


class AsyncRedisService:
    """
    Thread-safe async Redis service using redis.asyncio
    Primary use case: PubSub operations that need to be thread-safe
    """

    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self.key_prefix = "runna"

    async def _get_client(self) -> redis.Redis:
        """Get or create async Redis client with connection pooling"""
        if self._client is None:
            self._pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                max_connections=20,
            )
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client

    async def close(self):
        """Clean up Redis connections"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    def _build_key(self, namespace: str, identifier: str) -> str:
        """Build prefixed key for namespacing"""
        return f"{self.key_prefix}:{namespace}:{identifier}"

    def _serialize(self, data: Any) -> str:
        """Serialize data to JSON string"""
        if isinstance(data, BaseModel):
            return data.model_dump_json()
        return json.dumps(data, default=str)

    def _deserialize(self, data: str) -> Any:
        """Deserialize JSON string to Python object"""
        return json.loads(data)

    async def publish(self, channel: str, message: Any) -> int:
        """
        Async publish message to Redis channel
        Returns number of subscribers that received the message
        """
        try:
            client = await self._get_client()
            channel_key = self._build_key("channel", channel)
            serialized_message = self._serialize(message)
            return await client.publish(channel_key, serialized_message)
        except redis.ConnectionError:
            return 0

    async def get_pubsub(self) -> Optional[redis.client.PubSub]:
        """
        Get async PubSub instance for subscribing to channels
        This is thread-safe unlike the sync version
        """
        try:
            client = await self._get_client()
            return client.pubsub()
        except redis.ConnectionError:
            return None

    async def subscribe_channel(
        self, pubsub: redis.client.PubSub, channel: str
    ) -> bool:
        """Subscribe to a Redis channel using async PubSub"""
        try:
            channel_key = self._build_key("channel", channel)
            await pubsub.subscribe(channel_key)
            return True
        except redis.ConnectionError:
            return False

    async def xadd(
        self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None
    ) -> Optional[str]:
        """Add message to Redis stream (async version)"""
        try:
            client = await self._get_client()
            stream_key = self._build_key("stream", stream)

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

            return await client.xadd(stream_key, serialized_fields, **kwargs)
        except redis.ConnectionError:
            return None

    async def xgroup_create(
        self, stream: str, group_name: str, id: str = "0", mkstream: bool = True
    ) -> bool:
        """Create consumer group for Redis stream (async version)"""
        try:
            client = await self._get_client()
            stream_key = self._build_key("stream", stream)
            await client.xgroup_create(stream_key, group_name, id=id, mkstream=mkstream)
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                return True
            return False
        except redis.ConnectionError:
            return False

    async def xreadgroup(
        self,
        group_name: str,
        consumer_name: str,
        streams: Dict[str, str],
        count: Optional[int] = None,
        block: Optional[int] = None,
    ) -> List:
        """Read messages from Redis stream consumer group (async version)"""
        try:
            client = await self._get_client()
            stream_keys = {
                self._build_key("stream", stream): stream_id
                for stream, stream_id in streams.items()
            }

            kwargs = {}
            if count is not None:
                kwargs["count"] = count
            if block is not None:
                kwargs["block"] = block

            result = await client.xreadgroup(
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

    async def xack(
        self, stream: str, group_name: str, message_ids: Union[str, List[str]]
    ) -> int:
        """Acknowledge Redis stream messages (async version)"""
        try:
            client = await self._get_client()
            stream_key = self._build_key("stream", stream)
            if isinstance(message_ids, str):
                message_ids = [message_ids]
            return await client.xack(stream_key, group_name, *message_ids)
        except redis.ConnectionError:
            return 0
