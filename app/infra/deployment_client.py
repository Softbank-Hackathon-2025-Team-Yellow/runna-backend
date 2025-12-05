import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.function import DeploymentStatus, Function
from app.models.job import Job, JobStatus, JobType

logger = logging.getLogger(__name__)


class DeploymentClient:
    """
    Deployment Future 관리 클라이언트
    
    execution_client.py의 Future 패턴을 배포에 적용:
    - deployment_futures: {job_id: asyncio.Future}
    - 배포 완료 시 Future.set_result()
    - 상태 조회 시 Future.done() 확인
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if DeploymentClient._initialized:
            return
        
        self.deployment_futures: Dict[int, asyncio.Future] = {}
        DeploymentClient._initialized = True
        logger.info("DeploymentClient initialized with Future tracking")
    
    async def deploy_async(
        self,
        job_id: int,
        function_id: UUID,
        custom_path: str,
        env_vars: Optional[Dict[str, str]] = None
    ):
        """
        백그라운드에서 배포 실행 후 Future 완료
        
        Args:
            job_id: Job ID (DB 세션 분리를 위해 ID로 조회)
            function_id: Function ID
            custom_path: 배포 경로
            env_vars: 환경 변수
        """
        from app.database import SessionLocal
        
        db = SessionLocal()
        function = None
        job = None
        
        try:
            logger.info(f"Starting deployment for job {job_id}, function {function_id}")
            
            # 0. Job 조회 (새로운 세션에서)
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            # 1. Function 조회
            function = db.query(Function).filter(Function.id == function_id).first()
            if not function:
                raise ValueError(f"Function {function_id} not found")
            
            # 2. 상태 업데이트: RUNNING
            job.status = JobStatus.RUNNING
            function.deployment_status = DeploymentStatus.DEPLOYING
            function.deployment_error = None
            db.commit()
            
            # 3. FunctionService를 통한 K8s 배포 실행 (레이어 분리)
            # asyncio.to_thread로 동기 함수를 비동기로 래핑 (이벤트 루프 블록 방지)
            from app.services.function_service import FunctionService
            
            function_service = FunctionService(db)
            deploy_result = await asyncio.to_thread(
                function_service.deploy_function_to_k8s,
                function_id=function_id,
                custom_path=custom_path,
                env_vars=env_vars
            )
            
            # 4. 성공 처리
            job.status = JobStatus.SUCCESS
            job.result = json.dumps(deploy_result)
            
            function.deployment_status = DeploymentStatus.DEPLOYED
            function.knative_url = deploy_result["ingress_url"]
            function.last_deployed_at = datetime.utcnow()
            function.deployment_error = None
            
            db.commit()
            
            # 5. Future 완료
            if job.id in self.deployment_futures:
                future = self.deployment_futures[job.id]
                if not future.done():
                    future.set_result({
                        "status": "success",
                        "result": deploy_result
                    })
            
            logger.info(f"Deployment successful for job {job.id}")
            
        except Exception as e:
            logger.error(f"Deployment failed for job {job_id}: {str(e)}")
            
            # 실패 처리
            if job:
                job.status = JobStatus.FAILED
                job.result = str(e)
            
            if function:
                function.deployment_status = DeploymentStatus.FAILED
                function.deployment_error = str(e)
            
            try:
                db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to commit error status: {commit_error}")
            
            # Future 예외 설정
            if job_id in self.deployment_futures:
                future = self.deployment_futures[job_id]
                if not future.done():
                    future.set_exception(e)
        finally:
            db.close()
    
    def get_deployment_status(self, job_id: int) -> Optional[str]:
        """
        Future 기반 실시간 상태 확인
        
        Args:
            job_id: Job ID
            
        Returns:
            "RUNNING", "SUCCESS", "FAILED" 또는 None (DB 조회 필요)
        """
        future = self.deployment_futures.get(job_id)
        if not future:
            return None  # Future 없음, DB에서 조회해야 함
        
        if future.done():
            try:
                future.result()  # 예외 발생 여부 확인
                return "SUCCESS"
            except Exception:
                return "FAILED"
        else:
            return "RUNNING"
    
    def cleanup_future(self, job_id: int):
        """완료된 Future 정리"""
        future = self.deployment_futures.pop(job_id, None)
        if future and not future.done():
            future.cancel()
