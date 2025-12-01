import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.infra.execution_client import ExecutionClient
from app.models.function import ExecutionType, Function
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate
from app.services.job_service import JobService


class ExecutionService:
    def __init__(self, db: Session, exec_client: ExecutionClient = None):
        """
        Initialize ExecutionService.

        Args:
            db: Database session
            exec_client: ExecutionClient instance (optional, for dependency injection)
                        If not provided, uses singleton instance
        """
        self.db = db
        self.exec_client = exec_client if exec_client is not None else ExecutionClient()

    async def execute_function(
        self, function_id: int, input_data: Dict[str, Any]
    ) -> Job:
        """
        ✅ Implemented: 함수를 실행합니다.

        sync 함수: Redis Stream에 넣고 Pub/Sub으로 결과 대기 → 200 + 결과
        async 함수: Redis Stream에 넣고 바로 반환 → 202 + Job ID

        변경사항:
          - 반환 타입을 Dict[str, Any]에서 Job으로 변경하여 타입이 지정된 SQLAlchemy 객체를 제공합니다.
          - Non-blocking I/O (Redis) 지원을 위해 async로 변경했습니다.
          - async wrapper (asyncio.to_thread)로 동기 Redis 호출을 처리합니다.
          - ExecutionClient를 의존성 주입으로 받아 테스트 가능성 향상
        """
        function = self.db.query(Function).filter(Function.id == function_id).first()
        if not function:
            raise ValueError("Function not found")

        _job = JobCreate(function_id=function.id, status=JobStatus.PENDING)

        job = Job(**_job.model_dump())

        try:
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
        except Exception:
            self.db.rollback()  # ✅ 롤백 추가
            raise  # ✅ 예외 재발생

        try:
            JobService(self.db).update_job_status(job.id, JobStatus.PENDING)
        except Exception as e:
            print(e)

        if function.execution_type == ExecutionType.SYNC:
            return await self._execute_sync(job, input_data)
        else:
            return await self._execute_async(job, input_data)

    async def _execute_sync(self, job: Job, input_data: Dict[str, Any]) -> Job:
        """
        ✅ Implemented: 동기 함수 실행 처리

        구현 완료:
        1. ExecutionClient.invoke_sync() 호출
        2. Waiters 맵으로 결과 대기 (최대 30초)
        3. 결과를 받아 Job 업데이트
        4. 200 OK + 결과 반환

        흐름:
        - Stream에 작업 추가
        - 백그라운드 리스너가 callback_channel에서 결과 수신
        - Waiters 맵에 결과 설정
        - invoke_sync가 결과 반환
        - Job status/result 업데이트 및 DB 저장

        변경사항: 일관성을 위해 반환 타입을 Dict에서 Job으로 변경했습니다.
        """
        try:
            # Sync execution: Stream에 넣고 Pub/Sub으로 결과 대기
            result = await self.exec_client.invoke_sync(job, input_data)

            # Check result status and update Job accordingly
            if result.get("status") == "success":
                job.status = JobStatus.SUCCESS  # ✅ SUCCEEDED → SUCCESS
                job.result = json.dumps(
                    result.get("result")
                )  # Save only the result field
            else:
                # Failed or any other status
                job.status = JobStatus.FAILED
                job.result = (
                    result.get("error") or result.get("result") or "Unknown error"
                )
        except Exception as e:
            # Update Job status to FAILED on exception
            job.status = JobStatus.FAILED
            job.result = str(e)

        self.db.commit()
        self.db.refresh(job)
        return job

    async def _execute_async(self, job: Job, input_data: Dict[str, Any]) -> Job:
        """
        ✅ Implemented: 비동기 함수 실행 처리

        구현 완료:
        1. Redis Stream에 작업 추가
        2. Job은 PENDING 상태로 유지
        3. 즉시 202 Accept + Job ID 반환
        4. 백그라운드 리스너가 callback_channel 구독 중

        TODO: [Optional] async 요청 DB 업데이트
        현재 리스너는 sync 요청(Waiters 맵)만 처리합니다.
        async 요청 시 Job entity를 자동으로 업데이트하려면
        리스너에 DB 세션 관리 추가 필요.

        현재 흐름:
        1. ✅ Stream에 작업 추가
        2. ⬜ Worker가 Stream에서 작업 읽어서 함수 실행 (KNative 연동 필요)
        3. ⬜ 함수 실행 완료 후 callback_channel에 결과 publish (Worker 구현 필요)
        4. ✅ 백그라운드 리스너가 메시지 수신
        5. ⬜ Job entity를 SUCCESS/FAILED로 업데이트 (DB 세션 필요)

        변경사항: 일관성을 위해 반환 타입을 Dict에서 Job으로 변경했습니다.
        """
        try:
            # Async execution: Stream에 작업 추가
            await self.exec_client.insert_exec_queue(job, input_data)

            # Job status remains PENDING to indicate it's in queue
            # TODO: [Teammate] 백그라운드 리스너가 SUCCESS/FAILED로 업데이트
        except Exception as e:
            # If enqueue fails, mark as FAILED
            job.status = JobStatus.FAILED
            job.result = f"Failed to enqueue: {str(e)}"

        self.db.commit()
        self.db.refresh(job)
        return job
