import json
import os
from typing import Any, Dict

import httpx
from app.models.job import Job
from app.schemas.message import Execution

from app.infra.redis_service import RedisService


from app.core.debug import Debug


class ExecutionClient:
    def __init__(self):
        def __init__(self):
        self.exec_stream_name = "exec_stream"
        self.callback_channel_name = "callback_channel"
        self.consumer_group_name = "exec_consumers"


    async def invoke_sync(self, job: Job, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        동기로 함수를 실행하고 결과를 반환합니다.
        Redis 큐에 작업을 넣고, 결과가 나올 때까지 기다립니다.
        """
        # TODO: [Teammate Task] Redis Pub/Sub 또는 Blocking Pop을 사용하여
        # 작업을 큐에 넣고, 결과를 기다리는 로직 구현 필요.
        # 현재는 인터페이스만 정의함.

        # 임시 구현: 비동기 큐에 넣고, 바로 더미 결과 반환 (테스트용)
        await self.insert_exec_queue(job, payload)

        # 실제로는 여기서 Redis 응답을 await 해야 함
        return {"status": "succeeded", "result": "Sync execution result (Mock)"}

    async def insert_exec_queue(self, job: Job, payload: Dict[str, Any]):
        """
        Redis Stream에 함수 실행 요청을 삽입합니다
        job : 생성한 Job Entity
        payload : 함수 실행 인자

        함수 실행 결과는 callback_channel pub/sub을 통해 받을 수 있습니다.
        """

        exec_msg = Execution(
            job_id=job.id,
            function_id=job.function_id,
            payload=payload,
        )

        try:
            redis_service.xgroup_create(
                self.exec_stream_name, self.consumer_group_name, id="0", mkstream=True
            )

            message_id = redis_service.xadd(
                self.exec_stream_name,
                {
                    "job_id": exec_msg.job_id,
                    "function_id": exec_msg.function_id,
                    "payload": exec_msg.payload,
                },
            )

            return message_id is not None

        except Exception as e:
            print(e)
            print(f"Execution Request Push Failed. (job: {job.id})")
            return False

    def insert_exec_queue(self, job: Job, payload: Dict[str, Any]):
        """
        Backward compatibility method - delegates to insert_exec_stream
        """
        return self.insert_exec_stream(job, payload)
