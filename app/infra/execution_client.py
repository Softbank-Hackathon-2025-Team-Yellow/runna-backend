from typing import Any, Dict

from app.models.job import Job
from app.schemas.message import Execution

from app.infra.redis_service import RedisService


from app.core.debug import Debug


class ExecutionClient:
    def __init__(self):
        self.exec_stream_name = "exec_stream"
        self.callback_channel_name = "callback_channel"
        self.consumer_group_name = "exec_consumers"

    @Debug
    def insert_exec_stream(self, job: Job, payload: Dict[str, Any]) -> bool:
        """
        Redis Stream에 함수 실행 요청을 삽입합니다
        job : 생성한 Job Entity
        payload : 함수 실행 인자

        함수 실행 결과는 callback_channel pub/sub을 통해 받을 수 있습니다.
        """
        redis_service = RedisService()

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
