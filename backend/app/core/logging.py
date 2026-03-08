"""
Structured logging utility with correlation ID support.

Provides correlation ID tracking (job_id, run_id, portfolio_id) for all log messages
using Python's standard logging module.
"""

import logging
from typing import Optional


class CorrelationAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter that injects correlation IDs into log messages.
    
    Correlation IDs (job_id, run_id, portfolio_id) are prepended to all log messages
    in the format: [job_id={job_id} run_id={run_id} portfolio_id={portfolio_id}]
    """

    def __init__(
        self,
        logger: logging.Logger,
        job_id: Optional[str] = None,
        run_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ):
        """
        Initialize the CorrelationAdapter.

        Args:
            logger: The underlying logger instance
            job_id: Optional job identifier
            run_id: Optional run identifier
            portfolio_id: Optional portfolio identifier
        """
        super().__init__(logger, {})
        self.job_id = job_id
        self.run_id = run_id
        self.portfolio_id = portfolio_id

    def process(self, msg: str, kwargs) -> tuple[str, dict]:
        """
        Process the logging message and inject correlation IDs.

        Args:
            msg: The log message
            kwargs: Additional keyword arguments

        Returns:
            Tuple of (processed_message, kwargs)
        """
        # Build correlation ID prefix
        correlation_parts = []
        if self.job_id is not None:
            correlation_parts.append(f"job_id={self.job_id}")
        if self.run_id is not None:
            correlation_parts.append(f"run_id={self.run_id}")
        if self.portfolio_id is not None:
            correlation_parts.append(f"portfolio_id={self.portfolio_id}")

        # Only add prefix if there are correlation IDs
        if correlation_parts:
            prefix = "[" + " ".join(correlation_parts) + "]"
            msg = f"{prefix} {msg}"

        return msg, kwargs


def get_logger(name: str) -> logging.Logger:
    """
    Get a standard logger instance.

    Args:
        name: The logger name (typically __name__)

    Returns:
        A logging.Logger instance
    """
    return logging.getLogger(name)


def with_correlation(
    logger: logging.Logger,
    job_id: Optional[str] = None,
    run_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
) -> CorrelationAdapter:
    """
    Wrap a logger with correlation ID context.

    Args:
        logger: The logger to wrap
        job_id: Optional job identifier
        run_id: Optional run identifier
        portfolio_id: Optional portfolio identifier

    Returns:
        A CorrelationAdapter instance with correlation IDs injected into log messages
    """
    return CorrelationAdapter(
        logger,
        job_id=job_id,
        run_id=run_id,
        portfolio_id=portfolio_id,
    )
