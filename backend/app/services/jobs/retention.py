"""
Retention Jobs - Automated cleanup of old execution logs.

Deletes ExecutionLog records older than 30 days to prevent unbounded growth.
"""
from datetime import datetime, timedelta

from sqlalchemy import func

from app.domain.models import ExecutionLog
from app.db.session import SessionLocal
from app.services.jobs import execution_logger


DEFAULT_RETENTION_DAYS = 30


async def cleanup_old_logs(retention_days: int = DEFAULT_RETENTION_DAYS) -> dict:
    """
    Delete ExecutionLog records older than the specified retention period.
    
    This function is wrapped by execution_logger to track its own execution.
    Deletes records where started_at is older than retention_days from now.
    
    Args:
        retention_days: Number of days to retain logs (default: 30)
    
    Returns:
        Dict with deletion statistics:
        - rows_deleted: Number of records deleted
        - retention_days: The retention period used
        - cutoff_date: ISO format date string of the cutoff
    
    Raises:
        Any exception is caught by execution_logger and recorded as FAILED.
    """
    async with execution_logger("cleanup_old_logs") as meta:
        session = SessionLocal()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Count records to be deleted
            count_result = session.query(func.count(ExecutionLog.execution_log_id)).filter(
                ExecutionLog.started_at < cutoff_date
            ).scalar()
            
            # Delete old records
            deleted = session.query(ExecutionLog).filter(
                ExecutionLog.started_at < cutoff_date
            ).delete(synchronize_session=False)
            
            session.commit()
            
            # Update execution meta with results
            meta.update({
                "rows_deleted": deleted,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "records_found": count_result
            })
            
            return {
                "rows_deleted": deleted,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        finally:
            session.close()
