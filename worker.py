#!/usr/bin/env python3
"""
Worker 프로세스 - Redis Stream에서 Job을 소비하고 실행하는 워커
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.infra.async_redis_service import AsyncRedisService
from app.models.job import JobStatus
from app.schemas.message import Callback, ExecutionStatus
from app.services.job_service import JobService


class FunctionExecutor:
    """함수 실행 추상화 인터페이스"""

    async def execute(self, function_id: int, payload: Dict[str, Any]) -> Any:
        """
        함수를 실행하고 결과를 반환합니다.
        현재는 더미 구현이며, 추후 KNative Serving 연동 예정
        """

        print("[DEBUG] payload received: ", payload)
        if payload and payload.get("test_time"):
            await asyncio.sleep(payload.get("test_time"))
        else:
            await asyncio.sleep(1)

        if payload and payload.get("test_error"):
            raise Exception(f"Test error for function {function_id}")

        return {
            "message": f"Function {function_id} executed successfully",
            "input": payload,
            "timestamp": datetime.now().isoformat(),
        }


class Worker:
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.async_redis_service = AsyncRedisService()
        self.executor = FunctionExecutor()
        self.running = False

        self.exec_stream_name = "exec_stream"
        self.callback_channel_name = "callback_channel"
        self.consumer_group_name = "exec_consumers"

    async def start(self):
        """워커 시작"""
        print(f"[DEBUG] Worker {self.worker_id} starting...")

        await self.async_redis_service.xgroup_create(
            self.exec_stream_name, self.consumer_group_name, id="0", mkstream=True
        )

        self.running = True
        await self._consume_loop()

    async def stop(self):
        """워커 정지"""
        print(f"[DEBUG] Worker {self.worker_id} stopping...")
        self.running = False
        # Redis 연결 정리
        await self.async_redis_service.close()

    async def _consume_loop(self):
        """Redis Stream 소비 루프"""
        print(
            f"[DEBUG] Worker {self.worker_id} started consuming from {self.exec_stream_name}"
        )

        while self.running:
            try:
                messages = await self.async_redis_service.xreadgroup(
                    self.consumer_group_name,
                    self.worker_id,
                    {self.exec_stream_name: ">"},
                    count=1,
                    block=1000,
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        await self._process_message(message_id, fields)

            except Exception as e:
                print(f"[DEBUG] Error in consume loop: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, message_id: str, fields: Dict[str, Any]):
        """개별 메시지 처리"""
        job_id = None
        try:
            job_id = int(fields.get("job_id"))
            function_id = int(fields.get("function_id"))
            payload = fields.get("payload")

            print(f"[DEBUG] Processing job {job_id} for function {function_id}")

            await self._update_job_status(job_id, JobStatus.RUNNING)

            result = await self.executor.execute(function_id, payload)

            await self._update_job_status(job_id, JobStatus.SUCCESS, json.dumps(result))
            await self._publish_callback(job_id, ExecutionStatus.SUCCESS, result)

        except Exception as e:
            error_msg = str(e)
            print(f"[DEBUG] Error processing job {job_id}: {error_msg}")

            if job_id:
                await self._update_job_status(job_id, JobStatus.FAILED, error_msg)
                await self._publish_callback(job_id, ExecutionStatus.FAILED, error_msg)

        finally:
            await self.async_redis_service.xack(
                self.exec_stream_name,
                self.consumer_group_name,
                message_id,
            )

    async def _update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        result: Optional[str] = None,
    ):
        """Job 상태 업데이트 - asyncio.to_thread로 동기 DB 호출 래핑"""

        def _sync_update_job_status():
            db = SessionLocal()
            try:
                job_service = JobService(db)
                job = job_service.update_job_status(job_id, status, result)
                return job
            except Exception as e:
                print(f"[DEBUG] Error updating job status: {e}")
                db.rollback()
                raise
            finally:
                db.close()

        try:
            await asyncio.to_thread(_sync_update_job_status)
        except Exception as e:
            print(f"[DEBUG] Failed to update job status for job {job_id}: {e}")

    async def _publish_callback(
        self, job_id: int, status: ExecutionStatus, result: Any
    ):
        """콜백 메시지 발행 - 완전 async Redis 호출"""

        try:
            callback = Callback(
                job_id=job_id,
                status=status,
                result=json.dumps(result) if result else None,
            )
            await self.async_redis_service.publish(
                self.callback_channel_name, callback.model_dump()
            )
        except Exception as e:
            print(f"[DEBUG] Error publishing callback for job {job_id}: {e}")


async def main():
    """메인 엔트리포인트"""
    worker = Worker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        print("[DEBUG]Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
