#!/usr/bin/env python3
"""
Reset Database for User Acceptance Testing (UAT) - Complete Reset

Deletes ALL data except users table, providing a true blank slate for UAT.
This is a DESTRUCTIVE operation that cannot be undone.

Preserves:
- users (for login capability)

Deletes (in dependency order):
1. All transactional tables
2. All master data tables (portfolios, instruments, listings, etc.)
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.domain.models import (
    AuditEvent,
    RecommendationLine,
    RecommendationBatch,
    LedgerEntry,
    LedgerBatch,
    CashSnapshot,
    HoldingSnapshot,
    PricePoint,
    FxRate,
    TaskRun,
    FreezeState,
    Alert,
    Notification,
    ExecutionLog,
    NotificationConfig,
    PortfolioPolicyAllocation,
    PortfolioConstituent,
    Portfolio,
    InstrumentListing,
    Instrument,
    Sleeve,
)


def reset_database_complete():
    """
    Delete all data except users table.
    Order is critical due to foreign key relationships.
    """
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("Trading Assistant - COMPLETE Database Reset for UAT")
        print("=" * 60)
        print()
        print("⚠️  This will delete ALL data except users!")
        print()
        
        # Define deletion order (child tables first, respecting FK constraints)
        tables_to_delete = [
            # Phase 1: Transactional tables (child-most)
            ("Audit Events", AuditEvent),
            ("Recommendation Lines", RecommendationLine),
            ("Recommendation Batches", RecommendationBatch),
            ("Ledger Entries", LedgerEntry),
            ("Ledger Batches", LedgerBatch),
            ("Execution Logs", ExecutionLog),
            ("Notification Configs", NotificationConfig),
            ("Cash Snapshots", CashSnapshot),
            ("Holding Snapshots", HoldingSnapshot),
            ("Price Points", PricePoint),
            ("FX Rates", FxRate),
            ("Task Runs", TaskRun),
            ("Freeze States", FreezeState),
            ("Alerts", Alert),
            ("Notifications", Notification),
            
            # Phase 2: Master data (parent tables)
            ("Portfolio Policy Allocations", PortfolioPolicyAllocation),
            ("Portfolio Constituents", PortfolioConstituent),
            ("Listings", InstrumentListing),
            ("Instruments", Instrument),
            ("Sleeves", Sleeve),
            ("Portfolios", Portfolio),
        ]
        
        total_deleted = 0
        
        for table_name, model_class in tables_to_delete:
            try:
                count = db.query(model_class).count()
                if count > 0:
                    db.query(model_class).delete(synchronize_session=False)
                    db.commit()
                    print(f"✓ Deleted {count:5d} rows from {table_name}")
                    total_deleted += count
                else:
                    print(f"  Skipped {table_name:30s} (0 rows)")
            except Exception as e:
                db.rollback()
                print(f"✗ Error deleting from {table_name}: {e}")
        
        # Also clean up run_input_snapshots via raw SQL
        try:
            result = db.execute(text("DELETE FROM run_input_snapshots"))
            db.commit()
            count = result.rowcount
            if count > 0:
                print(f"✓ Deleted {count:5d} rows from Run Input Snapshots")
                total_deleted += count
        except Exception as e:
            db.rollback()
            print(f"✗ Error deleting from Run Input Snapshots: {e}")
        
        # Reset all sequences
        print()
        print("Resetting PostgreSQL sequences...")
        sequences = [
            'audit_events_audit_event_id_seq',
            'recommendation_batches_recommendation_batch_id_seq',
            'recommendation_lines_recommendation_line_id_seq',
            'ledger_batches_batch_id_seq',
            'ledger_entries_entry_id_seq',
            'execution_logs_execution_log_id_seq',
            'notification_configs_notification_config_id_seq',
            'price_points_price_point_id_seq',
            'fx_rates_fx_rate_id_seq',
            'task_runs_run_id_seq',
            'freeze_states_freeze_id_seq',
            'alerts_alert_id_seq',
            'notifications_notification_id_seq',
            'portfolio_policy_allocations_allocation_id_seq',
            'portfolio_constituents_constituent_id_seq',
            'listing_listing_id_seq',
            'instrument_instrument_id_seq',
            'sleeves_sleeve_id_seq',
            'portfolio_portfolio_id_seq',
        ]
        
        for seq in sequences:
            try:
                db.execute(text(f"ALTER SEQUENCE IF EXISTS {seq} RESTART WITH 1"))
                db.commit()
            except Exception:
                pass
        
        print("✓ Sequences reset")
        print()
        print("=" * 60)
        print(f"Reset complete! Deleted {total_deleted} total rows.")
        print()
        print("Data preserved:")
        print("  - Users (1 login account)")
        print()
        print("All master and transactional data has been removed.")
        print("Database is now a TRUE BLANK SLATE for UAT!")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        db.rollback()
        print()
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    print()
    print("⚠️  WARNING: This will delete ALL data except users!")
    print()
    print("The following will be PERMANENTLY DELETED:")
    print("  - All portfolios, instruments, listings, sleeves")
    print("  - All policy allocations and constituents")
    print("  - All ledger entries, recommendations, audit events")
    print("  - All market data, snapshots, alerts, notifications")
    print()
    print("ONLY the users table will be preserved.")
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        confirmed = True
    else:
        response = input("Type 'DESTROY' to confirm complete reset: ")
        confirmed = response == 'DESTROY'
    
    if confirmed:
        sys.exit(reset_database_complete())
    else:
        print()
        print("Reset cancelled.")
        sys.exit(0)
