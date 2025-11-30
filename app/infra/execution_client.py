from typing import Union, Dict, Any

from app.models.job import Job


class ExecutionClient:

    async def insert_exec_queue(job: Job, payload: Dict[str, Any]):
        """
        비동기로 실행 큐에 요청을 삽입합니다
        job : 생성한 Job Entity
        payload : 함수 실행 인자

        함수 실행 결과는 job_completed pub/sub을 통해 받을 수 있습니다.
        """
        pass
