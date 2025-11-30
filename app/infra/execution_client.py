from typing import Any, Dict

from app.models.job import Job
from app.schemas.message import Execution

from app.infra.redis_service import RedisService


from app.core.debug import Debug


class ExecutionClient:
    def __init__(self):
        self.exec_q_name = "exec"
        self.callback_q_name = "callback"
        self.key = "stream"

    @Debug
    def insert_exec_queue(self, job: Job, payload: Dict[str, Any]):
        """
        비동기로 실행 큐에 요청을 삽입합니다
        job : 생성한 Job Entity
        payload : 함수 실행 인자

        함수 실행 결과는 job_completed pub/sub을 통해 받을 수 있습니다.
        """

        redis_service = RedisService()

        exec_msg = Execution(
            job_id=job.id,
            function_id=job.function_id,
            payload=payload,
        )

        try:
            redis_service.lpush(self.exec_q_name, self.key, exec_msg)

        except Exception as e:
            print(e)
            print(f"Execution Request Push Failed. (job: {job.id})")
