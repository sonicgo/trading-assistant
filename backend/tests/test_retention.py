"""
Tests for Phase 5/6 Chunk 2: Execution Capture & Retention

Tests the ExecutionLog model, execution logger utility, and retention job.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

from app.domain.models import ExecutionLog
from app.services.jobs.retention import cleanup_old_logs, DEFAULT_RETENTION_DAYS


@pytest.mark.asyncio
async def test_cleanup_old_logs_deletes_records_older_than_retention_period(db):
    """Test that cleanup_old_logs deletes records older than the retention period."""
    # Clean up any existing execution logs from previous runs
    db.query(ExecutionLog).delete()
    db.commit()

    # Create old records (older than 30 days)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)
    for i in range(5):
        log = ExecutionLog(
            job_name="test_job",
            status="SUCCESS",
            started_at=old_date - timedelta(hours=i)
        )
        db.add(log)
    
    # Create recent records (within retention period)
    recent_date = datetime.now(timezone.utc) - timedelta(days=5)
    for i in range(3):
        log = ExecutionLog(
            job_name="test_job",
            status="SUCCESS",
            started_at=recent_date - timedelta(hours=i)
        )
        db.add(log)
    
    db.commit()
    
    # Verify initial count
    initial_count = db.query(ExecutionLog).count()
    assert initial_count == 8
    
    # Run cleanup
    result = await cleanup_old_logs(retention_days=DEFAULT_RETENTION_DAYS)
    
    # Verify results
    assert result["rows_deleted"] == 5
    assert result["retention_days"] == DEFAULT_RETENTION_DAYS
    
    # Verify remaining records (3 recent test records + 1 cleanup job log)
    remaining_count = db.query(ExecutionLog).count()
    assert remaining_count == 4

    # Verify only recent records remain (excluding the cleanup job log itself)
    test_records = db.query(ExecutionLog).filter(
        ExecutionLog.job_name == "test_job"
    ).all()
    for record in test_records:
        assert record.started_at > datetime.now(timezone.utc) - timedelta(days=DEFAULT_RETENTION_DAYS)


@pytest.mark.asyncio
async def test_cleanup_old_logs_with_custom_retention(db):
    """Test that cleanup respects custom retention period."""
    # Clean up existing logs
    db.query(ExecutionLog).delete()
    db.commit()

    # Create records at various ages
    for days_ago in [5, 10, 15, 20, 25]:
        log = ExecutionLog(
            job_name="test_job",
            status="SUCCESS",
            started_at=datetime.now(timezone.utc) - timedelta(days=days_ago)
        )
        db.add(log)
    
    db.commit()
    
    # Run cleanup with 12 day retention
    result = await cleanup_old_logs(retention_days=12)
    
    # Should delete records older than 12 days (15, 20, 25 = 3 records)
    assert result["rows_deleted"] == 3

    # Verify remaining (2 test records < 12 days + 1 cleanup job log)
    remaining = db.query(ExecutionLog).count()
    assert remaining == 3


@pytest.mark.asyncio
async def test_cleanup_old_logs_no_records_to_delete(db):
    """Test cleanup when no records match deletion criteria."""
    # Clean up existing logs
    db.query(ExecutionLog).delete()
    db.commit()

    # Create only recent records
    for i in range(3):
        log = ExecutionLog(
            job_name="test_job",
            status="SUCCESS",
            started_at=datetime.now(timezone.utc) - timedelta(days=i)
        )
        db.add(log)
    
    db.commit()
    
    result = await cleanup_old_logs(retention_days=DEFAULT_RETENTION_DAYS)
    
    assert result["rows_deleted"] == 0
    # 3 test records + 1 cleanup job log
    assert db.query(ExecutionLog).count() == 4


@pytest.mark.asyncio
async def test_cleanup_old_logs_creates_execution_log_entry(db):
    """Test that the cleanup job itself is logged in ExecutionLog."""
    db.query(ExecutionLog).delete()
    db.commit()

    # Run cleanup
    await cleanup_old_logs(retention_days=DEFAULT_RETENTION_DAYS)
    
    # Refresh session to see committed log
    db.expire_all()
    
    # Find the log entry for the cleanup job
    cleanup_log = db.query(ExecutionLog).filter(
        ExecutionLog.job_name == "cleanup_old_logs"
    ).first()
    
    assert cleanup_log is not None
    assert cleanup_log.status == "SUCCESS"
    assert cleanup_log.completed_at is not None
    assert cleanup_log.meta is not None
    assert "rows_deleted" in cleanup_log.meta
    assert "retention_days" in cleanup_log.meta


def test_execution_log_model_creation(db):
    """Test basic ExecutionLog model creation."""
    # Clean up existing logs
    db.query(ExecutionLog).delete()
    db.commit()

    log = ExecutionLog(
        job_name="test_job",
        status="RUNNING",
        started_at=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()
    
    retrieved = db.query(ExecutionLog).first()
    assert retrieved.job_name == "test_job"
    assert retrieved.status == "RUNNING"
    assert retrieved.execution_log_id is not None


def test_execution_log_model_with_error(db):
    """Test ExecutionLog model with error message."""
    db.query(ExecutionLog).delete()
    db.commit()

    log = ExecutionLog(
        job_name="failing_job",
        status="FAILED",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        error_message="ValueError: Something went wrong\nTraceback:..."
    )
    db.add(log)
    db.commit()
    
    retrieved = db.query(ExecutionLog).first()
    assert retrieved.status == "FAILED"
    assert "ValueError" in retrieved.error_message


def test_execution_log_model_with_meta(db):
    """Test ExecutionLog model with metadata."""
    db.query(ExecutionLog).delete()
    db.commit()

    log = ExecutionLog(
        job_name="test_job",
        status="SUCCESS",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        meta={"rows_deleted": 100, "retention_days": 30}
    )
    db.add(log)
    db.commit()
    
    retrieved = db.query(ExecutionLog).first()
    assert retrieved.meta["rows_deleted"] == 100
    assert retrieved.meta["retention_days"] == 30
