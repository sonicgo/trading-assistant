"""
Execution Logger - Context Manager and Decorator for Automated Jobs

Wraps scheduled jobs to track execution status in the database.
"""
import uuid
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.domain.models import ExecutionLog
from app.db.session import SessionLocal


@asynccontextmanager
async def execution_logger(
    job_name: str,
    db: Optional[AsyncSession] = None,
    meta: Optional[dict] = None
):
    """
    Async context manager that logs job execution to the database.
    
    Creates a RUNNING record when entering, updates to SUCCESS or FAILED when exiting.
    Captures full traceback on failure.
    
    Usage:
        async with execution_logger("cleanup_old_logs") as log:
            result = await cleanup_function()
            log["rows_deleted"] = result
    
    Args:
        job_name: Identifier for the job being executed
        db: Optional database session (creates new one if not provided)
        meta: Optional initial metadata to store with the log
    
    Yields:
        Dict that can be updated with additional metadata during execution
    """
    log_record = None
    session = db
    session_created = False
    
    if session is None:
        session = SessionLocal()
        session_created = True
    
    try:
        # Create RUNNING record
        log_record = ExecutionLog(
            execution_log_id=uuid.uuid4(),
            job_name=job_name,
            status="RUNNING",
            started_at=datetime.utcnow(),
            meta=meta or {}
        )
        session.add(log_record)
        session.commit()
        
        # Yield mutable meta dict for the job to update
        execution_meta = dict(log_record.meta or {})
        
        try:
            yield execution_meta
            # Success path
            log_record.status = "SUCCESS"
            log_record.completed_at = datetime.utcnow()
            log_record.meta = execution_meta
            session.commit()
            
        except Exception as e:
            # Failure path - capture error details
            log_record.status = "FAILED"
            log_record.completed_at = datetime.utcnow()
            log_record.error_message = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            log_record.meta = execution_meta
            session.commit()
            raise
            
    finally:
        if session_created and session:
            session.close()


def with_execution_logging(job_name: str):
    """
    Decorator that wraps async functions with execution logging.
    
    Usage:
        @with_execution_logging("cleanup_old_logs")
        async def cleanup_old_logs():
            # Job logic here
            return {"rows_deleted": 100}
    
    Args:
        job_name: Identifier for the job
    
    Returns:
        Decorated function that logs execution to database
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with execution_logger(job_name) as meta:
                result = await func(*args, **kwargs)
                # If function returns a dict, merge it into meta
                if isinstance(result, dict):
                    meta.update(result)
                return result
        return wrapper
    return decorator
