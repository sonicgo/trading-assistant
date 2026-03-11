"""
Ledger Import Service - Phase 3 Book of Record

CSV import pathway following Playbook Section 8.
Implements preview -> apply flow with delta-planning algorithm.

Key principles:
- Import NEVER mutates snapshots directly
- Import only proposes ledger entries that get applied via standard posting service
- Version drift detection prevents stale applies
- All CSV parsing uses header names, not column positions
"""
import base64
import csv
import hashlib
import io
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.domain.models import (
    InstrumentListing,
    CashSnapshot,
    HoldingSnapshot,
    Portfolio,
)
from app.schemas.ledger import (
    CsvImportProfile,
    CsvImportPreviewResponse,
    CsvImportApplyRequest,
    CsvImportApplyResponse,
    ImportTargetHolding,
    ImportNormalizedTargets,
    ImportBasisVersion,
    ImportSummary,
    ImportValidationError,
    ImportValidationWarning,
    ProposedLedgerEntry,
    EntryKind,
    BatchSource,
    LedgerBatchCreate,
    LedgerEntryCreate,
    CashSnapshotResponse,
    HoldingSnapshotResponse,
)
from app.services.ledger_posting import post_ledger_batch
from app.services.snapshots import get_or_create_cash_snapshot, get_or_create_holding_snapshot


# CSV Profile: positions_gbp_v1
POSITIONS_GBP_V1_HEADERS = [
    "Investment",
    "Quantity",
    "Price",
    "Value (£)",
    "Cost (£)",
    "Change (£)",
    "Change (%)",
    "Price +/- today (%)",
    "Valuation currency",
    "Market currency",
    "Exchange rate",
    "Date",
    "Time",
    "Portfolio",
    "Ticker",
]

REQUIRED_COLUMNS = [
    "Investment",
    "Quantity",
    "Value (£)",
    "Cost (£)",
    "Date",
    "Time",
    "Portfolio",
    "Valuation currency",
    "Market currency",
    "Exchange rate",
]


def _normalize_numeric(value: str) -> Decimal:
    """
    Normalize numeric string that may contain thousands separators.
    
    Args:
        value: String containing numeric value (e.g., "1,234.56" or "1234.56")
        
    Returns:
        Decimal value
        
    Raises:
        ValueError: If value cannot be parsed as numeric
    """
    if value is None or value.strip() == "":
        raise ValueError("Empty value")

    cleaned = value.replace(",", "").strip()

    try:
        return Decimal(cleaned)
    except InvalidOperation as e:
        raise ValueError(f"Invalid numeric value: {value}") from e


def _parse_date_time(date_str: str, time_str: str) -> datetime:
    """
    Parse date and time strings into UTC datetime.
    
    Expected format: "10-Mar-26" + "17:07"
    Interpreted in Europe/London timezone, converted to UTC.
    
    Args:
        date_str: Date string (e.g., "10-Mar-26")
        time_str: Time string (e.g., "17:07")
        
    Returns:
        UTC datetime
        
    Raises:
        ValueError: If parsing fails
    """
    try:
        datetime_str = f"{date_str} {time_str}"
        dt = datetime.strptime(datetime_str, "%d-%b-%y %H:%M")
        london_tz = ZoneInfo("Europe/London")
        dt = dt.replace(tzinfo=london_tz)
        return dt.astimezone(timezone.utc)
    except ValueError as e:
        raise ValueError(f"Failed to parse date/time: {date_str} {time_str}") from e


def _calculate_sha256(content: bytes) -> str:
    """Calculate SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def _resolve_listing_by_ticker(db: Session, ticker: str) -> Optional[InstrumentListing]:
    """
    Resolve a ticker to a listing_id.
    
    Args:
        db: SQLAlchemy session
        ticker: Ticker symbol
        
    Returns:
        InstrumentListing or None if not found
        
    Raises:
        ValueError: If multiple listings found for same ticker
    """
    listings = db.query(InstrumentListing).filter(
        InstrumentListing.ticker == ticker
    ).all()

    if len(listings) == 0:
        return None

    if len(listings) > 1:
        primary_listings = [l for l in listings if l.is_primary]
        if len(primary_listings) == 1:
            return primary_listings[0]
        raise ValueError(f"Multiple listings found for ticker: {ticker}")

    return listings[0]


def _classify_row(row: dict) -> str:
    """
    Classify a CSV row as 'cash' or 'holding'.

    Args:
        row: Dictionary representing CSV row

    Returns:
        'cash' or 'holding'
    """
    investment = (row.get("Investment") or "").strip()
    ticker = (row.get("Ticker") or "").strip()

    if investment == "Cash GBP" and not ticker:
        return "cash"

    if ticker and investment != "Cash GBP":
        return "holding"

    if ticker:
        return "holding"

    return "unknown"


def _validate_row(
    row: dict,
    row_number: int,
    errors: list,
    warnings: list,
) -> bool:
    """
    Validate a single CSV row.
    
    Returns:
        True if valid, False if errors found
    """
    row_type = _classify_row(row)
    
    if row_type == "unknown":
        errors.append(ImportValidationError(
            row_number=row_number,
            field="Investment/Ticker",
            message="Row cannot be classified as cash or holding",
        ))
        return False
    
    # Validate currency fields (must be GBP for V1)
    valuation_ccy = (row.get("Valuation currency") or "").strip()
    market_ccy = (row.get("Market currency") or "").strip()
    
    if valuation_ccy != "GBP":
        errors.append(ImportValidationError(
            row_number=row_number,
            field="Valuation currency",
            message=f"Valuation currency must be GBP, got: {valuation_ccy}",
        ))
    
    if market_ccy != "GBP":
        errors.append(ImportValidationError(
            row_number=row_number,
            field="Market currency",
            message=f"Market currency must be GBP, got: {market_ccy}",
        ))
    
    # Validate exchange rate (must be 1 for GBP/GBP)
    try:
        fx_rate = _normalize_numeric(row.get("Exchange rate", "1"))
        if fx_rate != Decimal("1"):
            errors.append(ImportValidationError(
                row_number=row_number,
                field="Exchange rate",
                message=f"Exchange rate must be 1 for GBP/GBP, got: {fx_rate}",
            ))
    except ValueError as e:
        errors.append(ImportValidationError(
            row_number=row_number,
            field="Exchange rate",
            message=f"Invalid exchange rate: {e}",
        ))
    
    if row_type == "holding":
        # Validate numeric fields
        try:
            quantity = _normalize_numeric(row.get("Quantity", ""))
            if quantity < 0:
                errors.append(ImportValidationError(
                    row_number=row_number,
                    field="Quantity",
                    message="Quantity cannot be negative",
                ))
        except ValueError as e:
            errors.append(ImportValidationError(
                row_number=row_number,
                field="Quantity",
                message=f"Invalid quantity: {e}",
            ))
        
        try:
            cost = _normalize_numeric(row.get("Cost (£)", ""))
            if cost < 0:
                errors.append(ImportValidationError(
                    row_number=row_number,
                    field="Cost (£)",
                    message="Cost cannot be negative",
                ))
        except ValueError as e:
            errors.append(ImportValidationError(
                row_number=row_number,
                field="Cost (£)",
                message=f"Invalid cost: {e}",
            ))
    
    return len([e for e in errors if e.row_number == row_number]) == 0


def preview_import(
    db: Session,
    portfolio_id: str,
    submitted_by_user_id: str,
    file_content_base64: str,
    csv_profile: CsvImportProfile = CsvImportProfile.POSITIONS_GBP_V1,
) -> CsvImportPreviewResponse:
    """
    Preview a CSV import without applying changes.
    
    Implements the delta-planning algorithm from Playbook Section 8.11.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of target portfolio
        submitted_by_user_id: UUID of user initiating import
        file_content_base64: Base64-encoded CSV file
        csv_profile: CSV profile to use
        
    Returns:
        CsvImportPreviewResponse with proposed entries and validation results
    """
    portfolio_uuid = uuid.UUID(portfolio_id)
    
    # Decode file content
    try:
        file_content = base64.b64decode(file_content_base64)
    except Exception as e:
        return CsvImportPreviewResponse(
            csv_profile=csv_profile,
            source_file_sha256="",
            portfolio_id=portfolio_uuid,
            portfolio_label="",
            effective_at=datetime.now(timezone.utc),
            basis=ImportBasisVersion(cash_snapshot_version=0, holding_versions={}),
            summary=ImportSummary(holding_rows=0, cash_rows=0, errors=1, warnings=0),
            normalized_targets=ImportNormalizedTargets(cash_target_gbp=Decimal("0"), holdings=[]),
            proposed_entries=[],
            warnings=[],
            errors=[ImportValidationError(
                row_number=None,
                field=None,
                message=f"Failed to decode base64 content: {e}",
            )],
            plan_hash="",
        )
    
    file_hash = _calculate_sha256(file_content)
    
    errors: list[ImportValidationError] = []
    warnings: list[ImportValidationWarning] = []
    
    # Parse CSV
    try:
        csv_text = file_content.decode("utf-8-sig")
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Validate headers
        headers = csv_reader.fieldnames or []
        missing_headers = [col for col in REQUIRED_COLUMNS if col not in headers]
        
        if missing_headers:
            errors.append(ImportValidationError(
                row_number=None,
                field=None,
                message=f"Missing required columns: {', '.join(missing_headers)}",
            ))
            
            return CsvImportPreviewResponse(
                csv_profile=csv_profile,
                source_file_sha256=file_hash,
                portfolio_id=portfolio_uuid,
                portfolio_label="",
                effective_at=datetime.now(timezone.utc),
                basis=ImportBasisVersion(cash_snapshot_version=0, holding_versions={}),
                summary=ImportSummary(holding_rows=0, cash_rows=0, errors=len(errors), warnings=0),
                normalized_targets=ImportNormalizedTargets(cash_target_gbp=Decimal("0"), holdings=[]),
                proposed_entries=[],
                warnings=[],
                errors=errors,
                plan_hash="",
            )
        
        rows = list(csv_reader)
    except Exception as e:
        errors.append(ImportValidationError(
            row_number=None,
            field=None,
            message=f"Failed to parse CSV: {e}",
        ))
        return CsvImportPreviewResponse(
            csv_profile=csv_profile,
            source_file_sha256=file_hash,
            portfolio_id=portfolio_uuid,
            portfolio_label="",
            effective_at=datetime.now(timezone.utc),
            basis=ImportBasisVersion(cash_snapshot_version=0, holding_versions={}),
            summary=ImportSummary(holding_rows=0, cash_rows=0, errors=len(errors), warnings=0),
            normalized_targets=ImportNormalizedTargets(cash_target_gbp=Decimal("0"), holdings=[]),
            proposed_entries=[],
            warnings=[],
            errors=errors,
            plan_hash="",
        )
    
    # Get portfolio info
    portfolio = db.query(Portfolio).filter(Portfolio.portfolio_id == portfolio_uuid).first()
    portfolio_label = portfolio.name if portfolio else ""
    
    # Classify and validate rows
    cash_rows = []
    holding_rows = []
    csv_portfolio_values = set()
    
    for i, row in enumerate(rows, start=2):  # Start at 2 (1 is header)
        row_type = _classify_row(row)
        
        if row_type == "cash":
            cash_rows.append((i, row))
        elif row_type == "holding":
            holding_rows.append((i, row))
        
        # Track portfolio values for consistency check
        portfolio_val = (row.get("Portfolio") or "").strip()
        if portfolio_val:
            csv_portfolio_values.add(portfolio_val)
        
        # Validate row
        _validate_row(row, i, errors, warnings)
    
    # Check for exactly one cash row
    if len(cash_rows) == 0:
        errors.append(ImportValidationError(
            row_number=None,
            field=None,
            message="No cash row found in CSV",
        ))
    elif len(cash_rows) > 1:
        errors.append(ImportValidationError(
            row_number=None,
            field=None,
            message=f"Multiple cash rows found ({len(cash_rows)}). Only one allowed.",
        ))
    
    # Check for mixed portfolio values
    if len(csv_portfolio_values) > 1:
        errors.append(ImportValidationError(
            row_number=None,
            field="Portfolio",
            message=f"Mixed portfolio values in file: {', '.join(csv_portfolio_values)}",
        ))
    
    # Parse effective_at from first row's Date/Time
    effective_at = datetime.now(timezone.utc)
    if rows:
        try:
            first_row = rows[0]
            effective_at = _parse_date_time(
                first_row.get("Date", ""),
                first_row.get("Time", ""),
            )
        except ValueError as e:
            errors.append(ImportValidationError(
                row_number=2,
                field="Date/Time",
                message=f"Invalid date/time format: {e}",
            ))
    
    # If errors found, return early
    if errors:
        return CsvImportPreviewResponse(
            csv_profile=csv_profile,
            source_file_sha256=file_hash,
            portfolio_id=portfolio_uuid,
            portfolio_label=portfolio_label,
            effective_at=effective_at,
            basis=ImportBasisVersion(cash_snapshot_version=0, holding_versions={}),
            summary=ImportSummary(
                holding_rows=len(holding_rows),
                cash_rows=len(cash_rows),
                errors=len(errors),
                warnings=len(warnings),
            ),
            normalized_targets=ImportNormalizedTargets(cash_target_gbp=Decimal("0"), holdings=[]),
            proposed_entries=[],
            warnings=warnings,
            errors=errors,
            plan_hash="",
        )
    
    # Parse cash target
    cash_target_gbp = Decimal("0")
    if cash_rows:
        try:
            cash_row = cash_rows[0][1]
            cash_target_gbp = _normalize_numeric(cash_row.get("Value (£)", "0"))
        except ValueError as e:
            errors.append(ImportValidationError(
                row_number=cash_rows[0][0],
                field="Value (£)",
                message=f"Invalid cash value: {e}",
            ))
    
    # Parse holdings and resolve listings
    target_holdings: list[ImportTargetHolding] = []
    seen_tickers = set()
    
    for row_number, row in holding_rows:
        ticker = (row.get("Ticker") or "").strip()
        
        # Check for duplicate tickers
        if ticker in seen_tickers:
            errors.append(ImportValidationError(
                row_number=row_number,
                field="Ticker",
                message=f"Duplicate ticker in file: {ticker}",
            ))
            continue
        seen_tickers.add(ticker)
        
        # Resolve listing
        listing = _resolve_listing_by_ticker(db, ticker)
        if listing is None:
            errors.append(ImportValidationError(
                row_number=row_number,
                field="Ticker",
                message=f"Unknown ticker: {ticker}",
            ))
            continue
        
        try:
            quantity = _normalize_numeric(row.get("Quantity", ""))
            book_cost = _normalize_numeric(row.get("Cost (£)", ""))
        except ValueError as e:
            errors.append(ImportValidationError(
                row_number=row_number,
                field="Quantity/Cost",
                message=f"Invalid numeric value: {e}",
            ))
            continue
        
        target_holdings.append(ImportTargetHolding(
            ticker=ticker,
            listing_id=listing.listing_id,
            target_quantity=quantity,
            target_book_cost_gbp=book_cost,
            investment_name=row.get("Investment", ""),
        ))
    
    # If errors found, return early
    if errors:
        return CsvImportPreviewResponse(
            csv_profile=csv_profile,
            source_file_sha256=file_hash,
            portfolio_id=portfolio_uuid,
            portfolio_label=portfolio_label,
            effective_at=effective_at,
            basis=ImportBasisVersion(cash_snapshot_version=0, holding_versions={}),
            summary=ImportSummary(
                holding_rows=len(holding_rows),
                cash_rows=len(cash_rows),
                errors=len(errors),
                warnings=len(warnings),
            ),
            normalized_targets=ImportNormalizedTargets(
                cash_target_gbp=cash_target_gbp,
                holdings=target_holdings,
            ),
            proposed_entries=[],
            warnings=warnings,
            errors=errors,
            plan_hash="",
        )
    
    # Get current snapshots for basis
    cash_snapshot = get_or_create_cash_snapshot(db, portfolio_uuid)
    basis = ImportBasisVersion(
        cash_snapshot_version=int(cash_snapshot.version_no),
        holding_versions={},
    )
    
    # Get current holdings for delta planning
    current_holdings = db.query(HoldingSnapshot).filter(
        HoldingSnapshot.portfolio_id == portfolio_uuid
    ).all()
    
    current_holdings_map = {h.listing_id: h for h in current_holdings}
    
    for holding in current_holdings:
        basis.holding_versions[str(holding.listing_id)] = int(holding.version_no)
    
    # Delta-planning algorithm (Playbook Section 8.11)
    proposed_entries: list[ProposedLedgerEntry] = []
    total_cash_impact_from_holdings = Decimal("0")
    
    for target in target_holdings:
        current = current_holdings_map.get(target.listing_id)
        
        current_qty = current.quantity if current else Decimal("0")
        current_book_cost = current.book_cost_gbp if current else Decimal("0")
        
        target_qty = target.target_quantity
        target_book_cost = target.target_book_cost_gbp
        
        delta_qty = target_qty - current_qty
        delta_cost = target_book_cost - current_book_cost
        
        # Case A: New or increased holding (delta_qty > 0)
        if delta_qty > 0:
            if delta_cost >= 0:
                # Standard BUY
                proposed_entries.append(ProposedLedgerEntry(
                    entry_kind=EntryKind.BUY,
                    listing_id=target.listing_id,
                    quantity_delta=delta_qty,
                    net_cash_delta_gbp=-delta_cost,
                    fee_gbp=Decimal("0"),
                    book_cost_delta_gbp=delta_cost,
                    note=f"Import BUY for {target.ticker}",
                ))
                total_cash_impact_from_holdings -= delta_cost
            else:
                # Negative cost delta - use ADJUSTMENT with warning
                proposed_entries.append(ProposedLedgerEntry(
                    entry_kind=EntryKind.ADJUSTMENT,
                    listing_id=target.listing_id,
                    quantity_delta=delta_qty,
                    net_cash_delta_gbp=-delta_cost,
                    fee_gbp=Decimal("0"),
                    book_cost_delta_gbp=delta_cost,
                    note=f"Import ADJUSTMENT for {target.ticker} (negative cost)",
                ))
                total_cash_impact_from_holdings -= delta_cost
                warnings.append(ImportValidationWarning(
                    row_number=None,
                    field=None,
                    message=f"Negative book cost delta for {target.ticker}, using ADJUSTMENT",
                ))
        
        # Case B: Reduced holding (delta_qty < 0)
        elif delta_qty < 0:
            # Calculate expected book cost reduction using current avg_cost
            current_avg_cost = current.book_cost_gbp / current.quantity if current and current.quantity > 0 else Decimal("0")
            sold_quantity = abs(delta_qty)
            expected_cost_reduction = (current_avg_cost * sold_quantity).quantize(Decimal("0.0000000001"))
            
            # Check if target residual book cost matches average-cost reduction
            target_residual_cost = target_book_cost
            expected_residual_cost = current_book_cost - expected_cost_reduction
            
            # Tolerance for floating point comparison
            tolerance = Decimal("0.01")
            cost_matches = abs(target_residual_cost - expected_residual_cost) <= tolerance
            
            if cost_matches:
                # Standard SELL
                cash_credit = expected_cost_reduction
                proposed_entries.append(ProposedLedgerEntry(
                    entry_kind=EntryKind.SELL,
                    listing_id=target.listing_id,
                    quantity_delta=delta_qty,
                    net_cash_delta_gbp=cash_credit,
                    fee_gbp=Decimal("0"),
                    book_cost_delta_gbp=-expected_cost_reduction,
                    note=f"Import SELL for {target.ticker}",
                ))
                total_cash_impact_from_holdings += cash_credit
            else:
                # Cost basis mismatch - use SELL + ADJUSTMENT or just ADJUSTMENT
                # For simplicity, use ADJUSTMENT for quantity and cost
                proposed_entries.append(ProposedLedgerEntry(
                    entry_kind=EntryKind.ADJUSTMENT,
                    listing_id=target.listing_id,
                    quantity_delta=delta_qty,
                    net_cash_delta_gbp=Decimal("0"),
                    fee_gbp=Decimal("0"),
                    book_cost_delta_gbp=delta_cost,
                    note=f"Import ADJUSTMENT for {target.ticker} (cost basis mismatch)",
                ))
                warnings.append(ImportValidationWarning(
                    row_number=None,
                    field=None,
                    message=f"Cost basis mismatch for {target.ticker}, using ADJUSTMENT",
                ))
        
        # Case C: Quantity unchanged, cost changed (delta_qty = 0, delta_cost != 0)
        elif delta_qty == 0 and delta_cost != 0:
            proposed_entries.append(ProposedLedgerEntry(
                entry_kind=EntryKind.ADJUSTMENT,
                listing_id=target.listing_id,
                quantity_delta=None,
                net_cash_delta_gbp=Decimal("0"),
                fee_gbp=Decimal("0"),
                book_cost_delta_gbp=delta_cost,
                note=f"Import ADJUSTMENT for {target.ticker} (cost-only change)",
            ))
        
        # Case D: Both unchanged - no action needed
    
    # Cash reconciliation rule (Playbook Section 8.12)
    # Simulate resulting cash from current cash + planned holding actions
    current_cash_balance = cash_snapshot.balance_gbp
    simulated_cash = current_cash_balance + total_cash_impact_from_holdings
    
    # Compare to imported cash target
    remaining_cash_delta = cash_target_gbp - simulated_cash
    
    if remaining_cash_delta > 0:
        # Positive delta => TOP_UP (materialized as CONTRIBUTION)
        proposed_entries.append(ProposedLedgerEntry(
            entry_kind=EntryKind.CONTRIBUTION,
            listing_id=None,
            quantity_delta=None,
            net_cash_delta_gbp=remaining_cash_delta,
            fee_gbp=Decimal("0"),
            book_cost_delta_gbp=None,
            note="Cash reconciliation - top up",
        ))
    elif remaining_cash_delta < 0:
        # Negative delta => cash-only ADJUSTMENT
        proposed_entries.append(ProposedLedgerEntry(
            entry_kind=EntryKind.ADJUSTMENT,
            listing_id=None,
            quantity_delta=None,
            net_cash_delta_gbp=remaining_cash_delta,
            fee_gbp=Decimal("0"),
            book_cost_delta_gbp=None,
            note="Cash reconciliation - adjustment",
        ))
    # If zero, no cash action needed
    
    # Calculate plan hash for idempotency
    plan_data = f"{file_hash}:{effective_at.isoformat()}:{len(proposed_entries)}"
    plan_hash = hashlib.sha256(plan_data.encode()).hexdigest()[:16]
    
    return CsvImportPreviewResponse(
        csv_profile=csv_profile,
        source_file_sha256=file_hash,
        portfolio_id=portfolio_uuid,
        portfolio_label=portfolio_label,
        effective_at=effective_at,
        basis=basis,
        summary=ImportSummary(
            holding_rows=len(holding_rows),
            cash_rows=len(cash_rows),
            errors=len(errors),
            warnings=len(warnings),
        ),
        normalized_targets=ImportNormalizedTargets(
            cash_target_gbp=cash_target_gbp,
            holdings=target_holdings,
        ),
        proposed_entries=proposed_entries,
        warnings=warnings,
        errors=errors,
        plan_hash=plan_hash,
    )


def apply_import(
    db: Session,
    portfolio_id: str,
    submitted_by_user_id: str,
    apply_request: CsvImportApplyRequest,
) -> CsvImportApplyResponse:
    """
    Apply a previously-previewed CSV import plan.
    
    Validates snapshot versions haven't drifted, then posts entries
    via the standard ledger posting service.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of target portfolio
        submitted_by_user_id: UUID of user applying import
        apply_request: The apply request with proposed entries and basis
        
    Returns:
        CsvImportApplyResponse with results
        
    Raises:
        ValueError: If snapshot versions have drifted (409 Conflict equivalent)
    """
    portfolio_uuid = uuid.UUID(portfolio_id)
    
    # Check for version drift
    current_cash = get_or_create_cash_snapshot(db, portfolio_uuid)
    current_cash_version = int(current_cash.version_no)
    
    if current_cash_version != apply_request.basis.cash_snapshot_version:
        raise ValueError(
            f"Cash snapshot version drift detected. "
            f"Expected {apply_request.basis.cash_snapshot_version}, got {current_cash_version}. "
            f"Please generate a fresh preview."
        )
    
    # Check holding versions
    for listing_id_str, expected_version in apply_request.basis.holding_versions.items():
        listing_uuid = uuid.UUID(listing_id_str)
        current_holding = get_or_create_holding_snapshot(db, portfolio_uuid, listing_uuid)
        
        if current_holding is None:
            current_version = 0
        else:
            current_version = int(current_holding.version_no)
        
        if current_version != expected_version:
            raise ValueError(
                f"Holding snapshot version drift detected for listing {listing_id_str}. "
                f"Expected {expected_version}, got {current_version}. "
                f"Please generate a fresh preview."
            )
    
    # Convert proposed entries to ledger entry creates
    ledger_entries = []
    for proposed in apply_request.proposed_entries:
        # CONTRIBUTION entries must not have fee_gbp (validation requirement)
        fee_gbp = None if proposed.entry_kind == EntryKind.CONTRIBUTION else proposed.fee_gbp
        ledger_entries.append(LedgerEntryCreate(
            entry_id=uuid.uuid4(),
            entry_kind=proposed.entry_kind,
            effective_at=apply_request.effective_at,
            listing_id=proposed.listing_id,
            quantity_delta=proposed.quantity_delta,
            net_cash_delta_gbp=proposed.net_cash_delta_gbp,
            fee_gbp=fee_gbp,
            book_cost_delta_gbp=proposed.book_cost_delta_gbp,
            note=proposed.note,
            meta=None,
        ))
    
    # Create batch request
    batch_request = LedgerBatchCreate(
        batch_id=uuid.uuid4(),
        idempotency_key=apply_request.idempotency_key,
        entries=ledger_entries,
        note=f"CSV Import: {apply_request.csv_profile.value}",
        meta={
            "csv_profile": apply_request.csv_profile.value,
            "source_file_sha256": apply_request.source_file_sha256,
            "plan_hash": apply_request.plan_hash,
        },
    )
    
    # Post via standard ledger posting service
    batch_response = post_ledger_batch(
        db=db,
        portfolio_id=portfolio_id,
        submitted_by_user_id=submitted_by_user_id,
        batch_request=batch_request,
        source=BatchSource.CSV_IMPORT,
    )
    
    # Get updated snapshots
    updated_cash = get_or_create_cash_snapshot(db, portfolio_uuid)
    updated_holdings = db.query(HoldingSnapshot).filter(
        HoldingSnapshot.portfolio_id == portfolio_uuid
    ).all()
    
    return CsvImportApplyResponse(
        batch_id=batch_response.batch_id,
        entries_posted=len(ledger_entries),
        cash_snapshot=CashSnapshotResponse(
            portfolio_id=portfolio_uuid,
            balance_gbp=updated_cash.balance_gbp,
            updated_at=updated_cash.updated_at,
            last_entry_id=updated_cash.last_entry_id,
            version_no=int(updated_cash.version_no),
        ),
        holding_snapshots=[
            HoldingSnapshotResponse(
                portfolio_id=h.portfolio_id,
                listing_id=h.listing_id,
                quantity=h.quantity,
                book_cost_gbp=h.book_cost_gbp,
                avg_cost_gbp=h.avg_cost_gbp,
                updated_at=h.updated_at,
                last_entry_id=h.last_entry_id,
                version_no=int(h.version_no),
            )
            for h in updated_holdings
        ],
    )
