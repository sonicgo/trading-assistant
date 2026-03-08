"""
Worker Runner — Entry Point

Run as: python -m app.worker.runner

Main loop: dequeues jobs from Redis, dispatches to handlers,
handles graceful shutdown on SIGINT/SIGTERM.
"""
import asyncio
import logging
import signal

from app.core.logging import get_logger, with_correlation
from app.queue.redis_queue import dequeue_job
from app.worker.price_refresh_worker import handle_price_refresh

logger = get_logger(__name__)


async def main() -> None:
    """Main worker loop — blocks until shutdown signal received."""
    # Configure basic logging so messages reach stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger.info("Worker starting...")

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    shutdown_event = asyncio.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        logger.info("Received signal %s, shutting down...", signum)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Worker ready, waiting for jobs...")

    # ── Poll loop ─────────────────────────────────────────────────────────────
    while not shutdown_event.is_set():
        try:
            # Blocking dequeue with 5-second timeout so the loop can
            # periodically check the shutdown event.
            job = dequeue_job(timeout=5)

            if job is None:
                # Timeout — check shutdown flag and loop again.
                continue

            # Attach correlation IDs for all downstream logging.
            ctx_logger = with_correlation(
                logger,
                job_id=job.job_id,
                portfolio_id=job.portfolio_id,
            )
            ctx_logger.info("Processing job: %s", job.task_kind)

            # ── Dispatch ──────────────────────────────────────────────────────
            if job.task_kind == "PRICE_REFRESH":
                await handle_price_refresh(job, ctx_logger)
            else:
                ctx_logger.warning("Unknown task_kind: %s — skipping", job.task_kind)

        except Exception as exc:
            # Log but do NOT crash the worker — keep looping.
            logger.error("Worker error: %s", exc, exc_info=True)

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
