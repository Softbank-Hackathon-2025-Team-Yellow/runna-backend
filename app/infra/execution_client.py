import json
import os
from typing import Any, Dict

import httpx
import redis
from app.models.job import Job


class ExecutionClient:
    _redis_client = None

    @classmethod
    def get_redis_client(cls):
        if cls._redis_client is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            cls._redis_client = redis.from_url(redis_url)
        return cls._redis_client

    @staticmethod
    async def invoke_sync(job: Job, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        동기로 함수를 실행하고 결과를 반환합니다.
        Redis 큐에 작업을 넣고, 결과가 나올 때까지 기다립니다.
        """
        # TODO: [Teammate Task] Redis Pub/Sub 또는 Blocking Pop을 사용하여
        # 작업을 큐에 넣고(insert_exec_queue 활용 가능), 결과를 기다리는 로직 구현 필요.
        # 현재는 인터페이스만 정의함.
        
        # 임시 구현: 비동기 큐에 넣고, 바로 더미 결과 반환 (테스트용)
        await ExecutionClient.insert_exec_queue(job, payload)
        
        # 실제로는 여기서 Redis 응답을 await 해야 함
        return {"status": "succeeded", "result": "Sync execution result (Mock)"}

    @classmethod
    async def insert_exec_queue(cls, job: Job, payload: Dict[str, Any]):
        """
        비동기로 실행 큐(Redis)에 요청을 삽입합니다.
        """
        try:
            client = cls.get_redis_client()
            message = {
                "job_id": job.id,
                "function_id": job.function_id,
                "payload": payload
            }
            # Redis List 'runna:jobs'에 Push
            client.rpush("runna:jobs", json.dumps(message))
        except Exception as e:
            print(f"Async enqueue failed: {e}")
            raise e

