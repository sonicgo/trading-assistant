"""Redis Queue implementation for job management."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis
from pydantic import BaseModel, Field

from app.core.config import settings


class JobPayload(BaseModel):
    """Job payload model for queue operations."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_kind: str  # e.g., "PRICE_REFRESH"
    portfolio_id: str
    requested_by_user_id: str
    enqueued_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class RedisQueue:
    """Redis-backed job queue."""

    def __init__(self, redis_url: str | None = None):
        """Initialize Redis queue.

        Args:
            redis_url: Redis connection URL. Defaults to settings.redis_url.
        """
        self.redis_url = redis_url or settings.redis_url
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self.queue_name = "ta:jobs"

    def enqueue_job(self, job: JobPayload) -> str:
        """Enqueue a job using LPUSH.

        Args:
            job: JobPayload instance to enqueue.

        Returns:
            The job_id of the enqueued job.
        """
        job_json = job.model_dump_json()
        self.client.lpush(self.queue_name, job_json)
        return job.job_id

    def dequeue_job(self, timeout: int = 5) -> Optional[JobPayload]:
        """Dequeue a job using BRPOP with blocking.

        Args:
            timeout: Timeout in seconds to wait for a job. Defaults to 5.

        Returns:
            JobPayload instance if a job is available, None if timeout.
        """
        result = self.client.brpop(self.queue_name, timeout=timeout)
        if result:
            # result is (queue_name, item)
            job_json = result[1]
            return JobPayload.model_validate_json(job_json)
        return None

    def get_queue_length(self) -> int:
        """Get current queue length.

        Returns:
            Number of jobs in the queue.
        """
        return self.client.llen(self.queue_name)


# Singleton instance
_queue_instance: RedisQueue | None = None


def get_queue() -> RedisQueue:
    """Get or create the global queue instance.

    Returns:
        RedisQueue singleton instance.
    """
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = RedisQueue()
    return _queue_instance


def enqueue_job(
    task_kind: str, portfolio_id: str, requested_by_user_id: str
) -> str:
    """Convenience function to create and enqueue a job.

    Args:
        task_kind: Type of task (e.g., "PRICE_REFRESH").
        portfolio_id: ID of the portfolio.
        requested_by_user_id: ID of the user requesting the task.

    Returns:
        The job_id of the enqueued job.
    """
    job = JobPayload(
        task_kind=task_kind,
        portfolio_id=portfolio_id,
        requested_by_user_id=requested_by_user_id,
    )
    return get_queue().enqueue_job(job)


def dequeue_job(timeout: int = 5) -> Optional[JobPayload]:
    """Convenience function to dequeue a job.

    Args:
        timeout: Timeout in seconds to wait for a job. Defaults to 5.

    Returns:
        JobPayload instance if a job is available, None if timeout.
    """
    return get_queue().dequeue_job(timeout=timeout)
