import asyncio
import json
import os
from typing import Any, Dict, Optional

import httpx
from app.models.job import Job, JobStatus
from app.schemas.message import Execution, Callback

from app.infra.redis_service import RedisService


from app.core.debug import Debug


class ExecutionClient:
    def __init__(self):
        self.redis_service = RedisService()
        self.exec_stream_name = "exec_stream"
        self.callback_channel_name = "callback_channel"
        self.consumer_group_name = "exec_consumers"
        self.waiters = {}  # {job_id: asyncio.Future} - sync 요청 대기용


    async def invoke_sync(self, job: Job, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implemented: 동기로 함수를 실행하고 결과를 반환합니다.

        Redis Stream에 작업을 넣고, Pub/Sub으로 결과가 올 때까지 기다립니다.

        흐름:
        1. Waiters 맵에 Future 등록
        2. Stream에 작업 추가
        3. 리스너가 callback_channel에서 결과를 받아 Future에 설정
        4. 최대 30초 대기 (timeout)
        5. 결과 반환 또는 timeout 에러

        start_callback_listener()가 백그라운드에서 실행되어야 합니다.
        """
        # Waiter 등록
        waiter = asyncio.Future()
        self.waiters[job.id] = waiter

        try:
            # Stream에 작업 추가
            await self.insert_exec_queue(job, payload)

            # 결과 대기 (timeout 30초)
            try:
                result = await asyncio.wait_for(waiter, timeout=30.0)
                return result
            except asyncio.TimeoutError:
                return {"status": "failed", "result": "Execution timeout (30s)"}
        finally:
            # Waiter 정리
            self.waiters.pop(job.id, None)

    async def insert_exec_queue(self, job: Job, payload: Dict[str, Any]):
        """
        Implemented: Redis Stream에 함수 실행 요청을 삽입합니다

        job : 생성한 Job Entity
        payload : 함수 실행 인자

        함수 실행 결과는 callback_channel pub/sub을 통해 받을 수 있습니다.

        async wrapper (asyncio.to_thread)를 사용하여
        동기 RedisService를 비동기 context에서 호출합니다.
        """

        exec_msg = Execution(
            job_id=job.id,
            function_id=job.function_id,
            payload=payload,
        )

        try:
            # async wrapper: 동기 Redis 호출을 별도 스레드에서 실행
            await asyncio.to_thread(
                self.redis_service.xgroup_create,
                self.exec_stream_name,
                self.consumer_group_name,
                id="0",
                mkstream=True
            )

            message_id = await asyncio.to_thread(
                self.redis_service.xadd,
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

    async def start_callback_listener(self):
        """
        Implemented: 백그라운드에서 callback_channel을 구독하여
        함수 실행 결과를 처리합니다.

        흐름:
        1. RedisService의 pub/sub 기능으로 callback_channel 구독
        2. 무한 루프로 메시지 수신
        3. Callback 메시지 파싱
        4. Waiters 맵 확인:
           - sync 요청: waiters[job_id]에 결과 설정
           - async 요청: TODO - DB에서 Job entity 업데이트 (DB 세션 필요)

        호출 위치:
            # main.py의 lifespan 이벤트에서 호출
            @asynccontextmanager
            async def lifespan(app: FastAPI):
                exec_client = ExecutionClient()
                asyncio.create_task(exec_client.start_callback_listener())
                yield
        """
        print(f"[Callback Listener] Starting... (channel: {self.callback_channel_name})")

        # Pub/Sub 객체 생성
        pubsub = await asyncio.to_thread(self.redis_service.get_pubsub)

        if not pubsub:
            print("[Callback Listener] Failed to create pubsub")
            return

        # 채널 구독
        await asyncio.to_thread(
            self.redis_service.subscribe_channel,
            pubsub,
            self.callback_channel_name
        )

        print(f"[Callback Listener] Subscribed to {self.callback_channel_name}")

        # 메시지 수신할 때까지 무한 루프
        while True:
            try:
                # 메시지 수신 (1초 timeout)
                message = await asyncio.to_thread(
                    pubsub.get_message,
                    timeout=1.0
                )

                if message and message['type'] == 'message':
                    try:
                        # Callback 파싱
                        callback_data = message['data']

                        # RedisService의 _deserialize 로직과 동일하게 파싱
                        if isinstance(callback_data, bytes):
                            callback_data = callback_data.decode('utf-8')

                        callback = Callback.model_validate_json(callback_data)

                        print(f"[Callback Listener] Received callback for job {callback.job_id}: {callback.status}")

                        # Waiters 맵 확인 (sync 요청용)
                        if callback.job_id in self.waiters:
                            waiter = self.waiters[callback.job_id]

                            # Future에 결과 설정
                            result = {
                                "status": callback.status.value,
                                "result": callback.result
                            }
                            waiter.set_result(result)

                            print(f"[Callback Listener] Set result for sync job {callback.job_id}")
                        else:
                            # async 요청: Job entity 업데이트
                            # TODO: DB 세션 관리 및 Job 업데이트 로직 필요
                            print(f"[Callback Listener] TODO: Update async job {callback.job_id} in DB")

                    except Exception as e:
                        print(f"[Callback Listener] Error processing message: {e}")

                # CPU 부하 감소
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"[Callback Listener] Error: {e}")
                await asyncio.sleep(1)
