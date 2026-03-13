"""
PRICE_REFRESH Worker Handler

Orchestrates the full ingest → DQ gate → alerts/freeze/notifications → audit pipeline
for a single PRICE_REFRESH job dequeued from Redis.

Session lifecycle:
  - Worker opens the session (SessionLocal()).
  - Worker commits on success, rolls back on failure.
  - Individual services (alerts, freeze) also commit their own rows because
    the current service implementations issue db.commit() internally.
    This is intentional: alert deduplication depends on rows being durable
    before the next dedup check.
  - TaskRun + RunInputSnapshot are committed in the final step.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger, with_correlation
from app.db.session import SessionLocal
from app.domain.models import Portfolio, RunInputSnapshot, TaskRun
from app.queue.redis_queue import JobPayload
from app.services.alerts import create_alert
from app.services.data_quality import evaluate_dq
from app.services.freeze import freeze_portfolio, is_portfolio_frozen
from app.services.market_data_ingest import IngestResult, ingest_prices_for_portfolio
from app.services.notifications import emit_notification
from app.services.providers.yfinance_adapter import YFinanceAdapter
from app.core.config import settings

logger = get_logger(__name__)


async def handle_price_refresh(job: JobPayload, ctx_logger: logging.Logger) -> str:
    """
    Handle a PRICE_REFRESH job end-to-end.

    Orchestration flow:
      1.  Open DB session (worker-managed lifecycle).
      2.  Ingest prices via MockProvider → IngestResult.
      3.  Evaluate DQ rules → list[DQViolation].
      4.  For each violation: create_alert() with dedup.
      5.  For each new CRITICAL alert: freeze_portfolio() + emit_notification().
      6.  Determine run status: SUCCESS / FROZEN / FAILED.
      7.  Write TaskRun + RunInputSnapshot.
      8.  Commit (or rollback + write FAILED TaskRun on exception).
      9.  Return run_id.

    Args:
        job:        Dequeued JobPayload from Redis.
        ctx_logger: Correlation-aware logger supplied by runner (carries job_id,
                    portfolio_id).  This function extends it with run_id.

    Returns:
        run_id (UUID string) of the TaskRun written to the database.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # Rebuild adapter with all three correlation IDs so every log line in this
    # function includes job_id, run_id AND portfolio_id.
    base_logger = ctx_logger.logger if isinstance(ctx_logger, logging.LoggerAdapter) else ctx_logger
    ctx_logger = with_correlation(
        base_logger,
        job_id=job.job_id,
        run_id=run_id,
        portfolio_id=job.portfolio_id,
    )

    ctx_logger.info("Starting PRICE_REFRESH job")

    db: Session = SessionLocal()

    try:
        adapter = YFinanceAdapter()
        ctx_logger.info("Using provider: %s", adapter.source_id)

        # ── 2. Ingest market data ──────────────────────────────────────────────
        ctx_logger.info("Ingesting prices for portfolio %s", job.portfolio_id)
        ingest_result: IngestResult = await ingest_prices_for_portfolio(
            db=db,
            adapter=adapter,
            portfolio_id=job.portfolio_id,
            job_id=job.job_id,
            want_close=True,
            want_intraday=True,
        )
        ctx_logger.info(
            "Ingest complete — prices_inserted=%d fx_inserted=%d errors=%d",
            ingest_result.prices_inserted,
            ingest_result.fx_inserted,
            len(ingest_result.errors),
        )
        if ingest_result.errors:
            for err in ingest_result.errors:
                ctx_logger.warning("Ingest error: %s", err)

        # ── 3. Evaluate data quality ───────────────────────────────────────────
        ctx_logger.info("Evaluating data quality...")
        violations = evaluate_dq(
            db=db,
            portfolio_id=job.portfolio_id,
            price_quotes=ingest_result.price_quotes,
            fx_quotes=ingest_result.fx_quotes,
            as_of=datetime.now(timezone.utc),
        )
        ctx_logger.info("DQ evaluation complete — violations=%d", len(violations))

        # ── 4 & 5. Process violations: alerts, freeze, notifications ──────────
        critical_count = 0

        for v in violations:
            ctx_logger.info(
                "DQ violation: rule=%s severity=%s listing=%s",
                v.rule_code,
                v.severity,
                v.listing_id,
            )

            if v.severity == "CRITICAL":
                critical_count += 1

            # create_alert() deduplicates: returns None if unresolved alert exists.
            alert = create_alert(
                db=db,
                portfolio_id=job.portfolio_id,
                listing_id=v.listing_id,
                severity=v.severity,
                rule_code=v.rule_code,
                title=v.title,
                message=v.message,
                details=v.details,
            )

            if alert is not None:
                ctx_logger.info(
                    "Alert created: alert_id=%s rule=%s severity=%s",
                    alert.alert_id,
                    v.rule_code,
                    v.severity,
                )

                if v.severity == "CRITICAL":
                    ctx_logger.warning(
                        "CRITICAL violation — freezing portfolio: rule=%s", v.rule_code
                    )
                    freeze_portfolio(
                        db=db,
                        portfolio_id=job.portfolio_id,
                        reason_alert_id=str(alert.alert_id),
                    )
                    ctx_logger.info("Portfolio frozen: portfolio_id=%s", job.portfolio_id)

                    portfolio = (
                        db.query(Portfolio)
                        .filter(Portfolio.portfolio_id == job.portfolio_id)
                        .first()
                    )
                    if portfolio is not None:
                        emit_notification(
                            db=db,
                            owner_user_id=str(portfolio.owner_user_id),
                            severity="CRITICAL",
                            title=f"Portfolio Frozen: {v.title}",
                            body=v.message,
                            meta={
                                "portfolio_id": job.portfolio_id,
                                "alert_id": str(alert.alert_id),
                                "run_id": run_id,
                                "rule_code": v.rule_code,
                            },
                        )
                        ctx_logger.info(
                            "Notification emitted: owner=%s", portfolio.owner_user_id
                        )
                    else:
                        ctx_logger.warning(
                            "Portfolio not found for notification: portfolio_id=%s",
                            job.portfolio_id,
                        )
            else:
                ctx_logger.info(
                    "Alert deduplicated (unresolved exists): rule=%s", v.rule_code
                )

        # ── 6. Determine run status ────────────────────────────────────────────
        # FROZEN: at least one CRITICAL violation AND portfolio is now frozen.
        # FAILED: violations exist but portfolio was not frozen
        #         (e.g. freeze already existed from a prior run).
        # SUCCESS: no violations.
        if critical_count > 0 and is_portfolio_frozen(db, job.portfolio_id):
            run_status = "FROZEN"
        elif len(violations) > 0:
            run_status = "FAILED"
        else:
            run_status = "SUCCESS"

        ctx_logger.info("Run status determined: status=%s", run_status)

        # ── 7. Write TaskRun ───────────────────────────────────────────────────
        task_run = TaskRun(
            run_id=uuid.UUID(run_id),
            job_id=uuid.UUID(job.job_id),
            task_kind="PRICE_REFRESH",
            portfolio_id=uuid.UUID(job.portfolio_id) if job.portfolio_id else None,
            status=run_status,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            summary={
                "prices_fetched": len(ingest_result.price_quotes),
                "prices_inserted": ingest_result.prices_inserted,
                "fx_fetched": len(ingest_result.fx_quotes),
                "fx_inserted": ingest_result.fx_inserted,
                "violations": len(violations),
                "critical_violations": critical_count,
                "errors": ingest_result.errors,
            },
        )
        db.add(task_run)
        db.flush()

        # ── 8. Write RunInputSnapshot ──────────────────────────────────────────
        input_snapshot = RunInputSnapshot(
            run_id=uuid.UUID(run_id),
            input_json={
                "portfolio_id": job.portfolio_id,
                "job_id": job.job_id,
                "task_kind": job.task_kind,
                "provider": adapter.source_id,
                "dq_config": {
                    "stale_max_minutes_intraday": settings.dq_stale_max_minutes_intraday,
                    "stale_max_days_close": settings.dq_stale_max_days_close,
                    "jump_threshold_pct": settings.dq_jump_threshold_pct,
                    "require_close": settings.dq_require_close,
                    "fx_stale_max_days": settings.dq_fx_stale_max_days,
                },
                "listings": [str(lst.listing_id) for lst in ingest_result.listings],
                "price_quotes": [
                    {
                        "listing_id": q.listing_id,
                        "price": q.price,
                        "currency": q.currency,
                        "is_close": q.is_close,
                        "as_of": q.as_of.isoformat(),
                    }
                    for q in ingest_result.price_quotes
                ],
                "fx_quotes": [
                    {
                        "base_ccy": q.base_ccy,
                        "quote_ccy": q.quote_ccy,
                        "rate": q.rate,
                        "as_of": q.as_of.isoformat(),
                    }
                    for q in ingest_result.fx_quotes
                ],
            },
            input_hash="",
        )
        db.add(input_snapshot)

        # ── Commit ────────────────────────────────────────────────────────────
        # NOTE: create_alert() and freeze_portfolio() each call db.commit()
        # internally for their own rows.  This final commit persists TaskRun
        # and RunInputSnapshot (plus any unflushed changes).
        db.commit()
        ctx_logger.info(
            "Job complete — run_id=%s status=%s", run_id, run_status
        )

        return run_id

    except Exception as exc:
        db.rollback()
        ctx_logger.error("Job failed: %s", exc, exc_info=True)

        try:
            failed_run = TaskRun(
                run_id=uuid.UUID(run_id),
                job_id=uuid.UUID(job.job_id),
                task_kind="PRICE_REFRESH",
                portfolio_id=uuid.UUID(job.portfolio_id) if job.portfolio_id else None,
                status="FAILED",
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                summary={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            db.add(failed_run)
            db.commit()
            ctx_logger.info("FAILED TaskRun written: run_id=%s", run_id)
        except Exception as inner_exc:
            ctx_logger.error(
                "Failed to write FAILED TaskRun: %s", inner_exc, exc_info=True
            )

        raise

    finally:
        db.close()
        ctx_logger.info("DB session closed: run_id=%s", run_id)
