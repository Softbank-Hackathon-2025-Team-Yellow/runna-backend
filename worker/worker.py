import asyncio
import json
import logging
import sys
import uuid
from typing import Dict, Any, Optional

sys.path.append('/home/ajy720/workspace/runna/backend')

from app.config import settings
from app.database import SessionLocal
from app.infra.async_redis_service import AsyncRedisService
from app.models.job import JobStatus
from app.schemas.message import Callback, ExecutionStatus
from app.services.job_service import JobService

# ORM 매핑을 위해 모든 모델 명시적 임포트
from app.models import function, job  # noqa: F401
from worker.executor import DummyExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.redis_service = AsyncRedisService()
        self.executor = DummyExecutor()
        self.running = False
        
        # 설정값들
        self.exec_stream_name = settings.exec_stream_name
        self.callback_channel_name = settings.callback_channel_name
        self.consumer_group_name = settings.consumer_group_name
        self.max_messages = settings.worker_max_messages
        self.block_time = settings.worker_block_time_ms

    async def start(self):
        """워커 시작"""
        logger.info(f"Worker {self.worker_id} starting...")
        
        # Consumer Group 생성 (이미 존재하면 무시)
        await self.redis_service.xgroup_create(
            self.exec_stream_name, 
            self.consumer_group_name, 
            id="0", 
            mkstream=True
        )
        
        self.running = True
        await self._consume_loop()

    async def stop(self):
        """워커 정지"""
        logger.info(f"Worker {self.worker_id} stopping...")
        self.running = False
        await self.redis_service.close()

    async def _consume_loop(self):
        """Redis Stream 소비 루프"""
        logger.info(
            f"Worker {self.worker_id} started consuming from {self.exec_stream_name}"
        )

        while self.running:
            try:
                messages = await self.redis_service.xreadgroup(
                    self.consumer_group_name,
                    self.worker_id,
                    {self.exec_stream_name: ">"},
                    count=self.max_messages,
                    block=self.block_time,
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        await self._process_message(message_id, fields)

            except Exception as e:
                logger.error(f"Error in consume loop: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, message_id: str, fields: Dict[str, Any]):
        """개별 메시지 처리"""
        job_id = None
        try:
            job_id = int(fields.get("job_id"))
            function_id = int(fields.get("function_id"))
            payload = fields.get("payload")

            logger.info(f"Processing job {job_id} for function {function_id}")

            # Job 상태를 RUNNING으로 업데이트
            await self._update_job_status(job_id, JobStatus.RUNNING)

            # 함수 실행
            execution_result: ExecutionResult = await self.executor.execute(function_id, payload)

            if execution_result.success:
                # 성공 시 처리
                await self._update_job_status(
                    job_id, 
                    JobStatus.SUCCESS, 
                    json.dumps(execution_result.result)
                )
                await self._publish_callback(
                    job_id, 
                    ExecutionStatus.SUCCESS, 
                    execution_result.result
                )
            else:
                # 실패 시 처리  
                await self._update_job_status(
                    job_id, 
                    JobStatus.FAILED, 
                    execution_result.error
                )
                await self._publish_callback(
                    job_id, 
                    ExecutionStatus.FAILED, 
                    execution_result.error
                )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing job {job_id}: {error_msg}")

            if job_id:
                await self._update_job_status(job_id, JobStatus.FAILED, error_msg)
                await self._publish_callback(job_id, ExecutionStatus.FAILED, error_msg)

        finally:
            # 메시지 ACK
            await self.redis_service.xack(
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
        """Job 상태 업데이트"""
        def _sync_update():
            db = SessionLocal()
            try:
                job_service = JobService(db)
                job_service.update_job_status(job_id, status, result)
                db.commit()
            except Exception as e:
                logger.error(f"Error updating job status: {e}")
                db.rollback()
                raise
            finally:
                db.close()

        try:
            await asyncio.to_thread(_sync_update)
        except Exception as e:
            logger.error(f"Failed to update job status for job {job_id}: {e}")

    async def _publish_callback(
        self, job_id: int, status: ExecutionStatus, result: Any
    ):
        """콜백 메시지 발행"""
        try:
            callback = Callback(
                job_id=job_id,
                status=status,
                result=json.dumps(result) if result else None,
                error=result if status == ExecutionStatus.FAILED else None,
            )
            await self.redis_service.publish(
                self.callback_channel_name, callback.model_dump()
            )
        except Exception as e:
            logger.error(f"Error publishing callback for job {job_id}: {e}")