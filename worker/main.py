#!/usr/bin/env python3
"""
Worker 메인 엔트리포인트
Redis Stream에서 Job을 소비하고 실행하는 워커 프로세스
"""

import asyncio
import logging
import signal
import sys

from app.config import settings
from worker.worker import Worker


def setup_logging():
    """로깅 설정"""
    log_level = getattr(settings, "log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


async def main():
    """메인 엔트리포인트"""
    setup_logging()
    logger = logging.getLogger(__name__)

    worker_id = getattr(settings, "worker_id", None)
    worker = Worker(worker_id)

    # 시그널 핸들러 설정
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting worker...")
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Worker error: {e}")
    finally:
        await worker.stop()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
