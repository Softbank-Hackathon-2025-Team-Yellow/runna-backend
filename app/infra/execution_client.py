import asyncio
from typing import Any, Dict

from app.infra.async_redis_service import AsyncRedisService
from app.models.job import Job
from app.schemas.message import Callback, Execution


class ExecutionClient:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 싱글톤 패턴으로 중복 초기화 방지
        if ExecutionClient._initialized:
            return

        self.async_redis_service = AsyncRedisService()  # 완전 async Redis 통합
        self.exec_stream_name = "exec_stream"
        self.callback_channel_name = "callback_channel"
        self.consumer_group_name = "exec_consumers"
        self.waiters = {}  # {job_id: asyncio.Future} - sync 요청 대기용

        ExecutionClient._initialized = True

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
        # Waiter 등록 및 Stream 작업 추가 (원자적 처리)
        loop = asyncio.get_running_loop()
        waiter = loop.create_future()

        try:
            # 1. 먼저 waiter 등록
            self.waiters[job.id] = waiter

            # 2. Stream에 작업 추가 (이미 waiter가 등록된 상태)
            await self.insert_exec_queue(job, payload)

            # 결과 대기 (timeout 30초)
            try:
                result = await asyncio.wait_for(waiter, timeout=30.0)
                return result
            except asyncio.TimeoutError:
                # 타임아웃 시 Future 취소
                if not waiter.done():
                    waiter.cancel()
                return {"status": "failed", "result": "Execution timeout (30s)"}
        finally:
            # Waiter 정리 - 완료되지 않은 Future 취소
            waiter = self.waiters.pop(job.id, None)
            if waiter and not waiter.done():
                waiter.cancel()

    async def insert_exec_queue(self, job: Job, payload: Dict[str, Any]):
        """
        Implemented: Redis Stream에 함수 실행 요청을 삽입합니다

        job : 생성한 Job Entity
        payload : 함수 실행 인자

        함수 실행 결과는 callback_channel pub/sub을 통해 받을 수 있습니다.

        완전 async Redis 호출로 성능 최적화
        """

        exec_msg = Execution(
            job_id=job.id,
            function_id=job.function_id,
            payload=payload,
        )

        try:
            # 완전 async Redis 호출 - asyncio.to_thread 오버헤드 제거
            await self.async_redis_service.xgroup_create(
                self.exec_stream_name,
                self.consumer_group_name,
                id="0",
                mkstream=True,
            )

            message_id = await self.async_redis_service.xadd(
                self.exec_stream_name,
                {
                    "job_id": exec_msg.job_id,
                    "function_id": exec_msg.function_id,
                    "payload": exec_msg.payload,
                },
            )

            return message_id is not None

        except Exception as e:
            print(f"Execution Request Push Failed. (job: {job.id})")
            # 오류 발생 시 waiter 제거
            self.waiters.pop(job.id, None)
            raise  # 오류를 상위로 전파

    async def start_callback_listener(self):
        """
        Thread-safe 백그라운드 callback 리스너
        AsyncRedisService를 사용하여 PubSub 스레드 경합 문제 해결

        개선사항:
        1. redis.asyncio를 사용하여 완전한 스레드 안전성 보장
        2. Future.set_result() 호출 전 done() 상태 체크
        3. 적절한 예외 처리 및 연결 복구 로직
        """
        print(
            f"[Callback Listener] Starting thread-safe listener... (channel: {self.callback_channel_name})"
        )

        while True:
            pubsub = None
            try:
                # 스레드 안전한 async PubSub 생성
                pubsub = await self.async_redis_service.get_pubsub()

                if not pubsub:
                    print(
                        "[Callback Listener] Failed to create async pubsub, retrying..."
                    )
                    await asyncio.sleep(5)
                    continue

                # 채널 구독
                success = await self.async_redis_service.subscribe_channel(
                    pubsub, self.callback_channel_name
                )

                if not success:
                    print("[Callback Listener] Failed to subscribe, retrying...")
                    await asyncio.sleep(5)
                    continue

                print(
                    f"[Callback Listener] Successfully subscribed to {self.callback_channel_name}"
                )

                # 메시지 수신 루프
                while True:
                    try:
                        # 비동기 메시지 수신
                        message = await pubsub.get_message(timeout=1.0)

                        if message and message["type"] == "message":
                            await self._process_callback_message(message)

                        # CPU 부하 감소
                        await asyncio.sleep(0.01)

                    except Exception as e:
                        print(f"[Callback Listener] Message processing error: {e}")
                        break  # 내부 루프 종료, 연결 재시도

            except Exception as e:
                print(f"[Callback Listener] Connection error: {e}")
            finally:
                # PubSub 연결 정리
                if pubsub:
                    try:
                        await pubsub.aclose()
                    except:
                        pass

                # 재연결 대기
                print("[Callback Listener] Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _process_callback_message(self, message):
        """콜백 메시지 처리 로직 분리"""
        try:
            # Callback 파싱
            callback_data = message["data"]

            # 바이너리 데이터 처리
            if isinstance(callback_data, bytes):
                callback_data = callback_data.decode("utf-8")

            callback = Callback.model_validate_json(callback_data)

            # Waiters 맵 확인 (sync 요청용)
            if callback.job_id in self.waiters:
                waiter = self.waiters[callback.job_id]

                # Future가 이미 완료되었는지 확인 (스레드 안전성)
                if not waiter.done():
                    result = {
                        "status": callback.status.value,
                        "result": callback.result,
                    }
                    waiter.set_result(result)
            else:
                # async 요청: Job entity 업데이트
                # TODO: DB 세션 관리 및 Job 업데이트 로직 필요
                pass

        except Exception as e:
            print(f"[Callback Listener] Error processing message: {e}")

    async def cleanup(self):
        """리소스 정리"""
        # 대기중인 모든 Future 취소
        for job_id, waiter in self.waiters.items():
            if not waiter.done():
                waiter.cancel()

        self.waiters.clear()

        # Redis 연결 정리
        await self.async_redis_service.close()

        # 싱글톤 인스턴스 리셋
        ExecutionClient._instance = None
        ExecutionClient._initialized = False
