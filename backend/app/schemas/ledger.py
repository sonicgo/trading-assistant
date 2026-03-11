"""
Ledger schemas for Book of Record (Phase 3).

Following patterns from Phase 3 Build Playbook Section 9:
- Decimal values serialize as strings (DecimalStr)
- Entry kinds: CONTRIBUTION, BUY, SELL, ADJUSTMENT, REVERSAL
- Batch operations are atomic
- CSV import uses preview -> apply flow
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ApiModel, DecimalStr


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EntryKind(str, Enum):
    """Canonical ledger entry types."""
    CONTRIBUTION = "CONTRIBUTION"
    BUY = "BUY"
    SELL = "SELL"
    ADJUSTMENT = "ADJUSTMENT"
    REVERSAL = "REVERSAL"


class BatchSource(str, Enum):
    """Source of ledger batch submission."""
    UI = "UI"
    CSV_IMPORT = "CSV_IMPORT"
    REVERSAL = "REVERSAL"


# ---------------------------------------------------------------------------
# Ledger Entry Schemas
# ---------------------------------------------------------------------------

class LedgerEntryCreate(ApiModel):
    """Single entry within a batch create request."""
    entry_id: uuid.UUID | None = Field(
        default=None,
        description="Optional client-generated UUID for idempotency. Server generates if not provided."
    )
    entry_kind: EntryKind
    effective_at: datetime
    listing_id: uuid.UUID | None = Field(
        default=None,
        description="Required for BUY, SELL, and most ADJUSTMENT entries"
    )
    quantity_delta: DecimalStr | None = Field(
        default=None,
        description="Signed quantity delta. Positive = buy/add, negative = sell/remove"
    )
    net_cash_delta_gbp: DecimalStr = Field(
        description="Signed final GBP cash impact. Negative for buy, positive for sell/contribution"
    )
    fee_gbp: DecimalStr | None = Field(
        default=None,
        description="Fee amount in GBP. Only allowed for BUY/SELL entries"
    )
    book_cost_delta_gbp: DecimalStr | None = Field(
        default=None,
        description="Explicit book cost delta. Used for ADJUSTMENT and REVERSAL entries"
    )
    note: str | None = None
    meta: dict[str, Any] | None = None


class LedgerEntryResponse(BaseModel):
    """Ledger entry as returned by API."""
    entry_id: uuid.UUID
    batch_id: uuid.UUID
    portfolio_id: uuid.UUID
    entry_kind: EntryKind
    effective_at: datetime
    listing_id: uuid.UUID | None
    quantity_delta: DecimalStr | None
    net_cash_delta_gbp: DecimalStr
    fee_gbp: DecimalStr | None
    book_cost_delta_gbp: DecimalStr | None
    reversal_of_entry_id: uuid.UUID | None
    created_at: datetime
    note: str | None
    meta: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Ledger Batch Schemas
# ---------------------------------------------------------------------------

class LedgerBatchCreate(ApiModel):
    """Request to create a new ledger batch with entries."""
    batch_id: uuid.UUID | None = Field(
        default=None,
        description="Optional client-generated UUID for idempotency"
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Optional idempotency key to prevent duplicate submissions"
    )
    entries: list[LedgerEntryCreate] = Field(
        min_length=1,
        description="One or more ledger entries to post atomically"
    )
    note: str | None = None
    meta: dict[str, Any] | None = None


class LedgerBatchResponse(BaseModel):
    """Ledger batch as returned by API."""
    batch_id: uuid.UUID
    portfolio_id: uuid.UUID
    submitted_by_user_id: uuid.UUID
    source: BatchSource
    created_at: datetime
    note: str | None
    meta: dict[str, Any] | None
    idempotency_key: str | None
    entries: list[LedgerEntryResponse]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Reversal Schemas
# ---------------------------------------------------------------------------

class LedgerReversalRequest(ApiModel):
    """Request to reverse one or more existing ledger entries."""
    batch_id: uuid.UUID | None = Field(
        default=None,
        description="Optional client-generated UUID for the reversal batch"
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Optional idempotency key to prevent duplicate reversals"
    )
    entry_ids: list[uuid.UUID] = Field(
        min_length=1,
        description="Entries to reverse. Each will generate a compensating entry."
    )
    note: str | None = Field(
        default=None,
        description="Explanation for the reversal"
    )


# ---------------------------------------------------------------------------
# Snapshot Schemas
# ---------------------------------------------------------------------------

class CashSnapshotResponse(BaseModel):
    """Current cash snapshot for a portfolio."""
    portfolio_id: uuid.UUID
    balance_gbp: DecimalStr
    updated_at: datetime
    last_entry_id: uuid.UUID | None
    version_no: int

    model_config = ConfigDict(from_attributes=True)


class HoldingSnapshotResponse(BaseModel):
    """Current holding snapshot for a portfolio/listing."""
    portfolio_id: uuid.UUID
    listing_id: uuid.UUID
    quantity: DecimalStr
    book_cost_gbp: DecimalStr
    avg_cost_gbp: DecimalStr
    updated_at: datetime
    last_entry_id: uuid.UUID | None
    version_no: int

    model_config = ConfigDict(from_attributes=True)


class HoldingSnapshotListResponse(BaseModel):
    """List of holding snapshots for a portfolio."""
    portfolio_id: uuid.UUID
    holdings: list[HoldingSnapshotResponse]
    total_book_cost_gbp: DecimalStr


# ---------------------------------------------------------------------------
# CSV Import Schemas
# ---------------------------------------------------------------------------

class CsvImportProfile(str, Enum):
    """Supported CSV import profiles."""
    POSITIONS_GBP_V1 = "positions_gbp_v1"


class CsvImportPreviewRequest(ApiModel):
    """Request to preview a CSV import."""
    csv_profile: CsvImportProfile = CsvImportProfile.POSITIONS_GBP_V1
    idempotency_key: str | None = None
    file_content_base64: str = Field(
        description="Base64-encoded CSV file content"
    )


class ImportTargetHolding(BaseModel):
    """Normalized holding target from CSV import."""
    ticker: str
    listing_id: uuid.UUID
    target_quantity: DecimalStr
    target_book_cost_gbp: DecimalStr
    investment_name: str


class ImportNormalizedTargets(BaseModel):
    """Normalized target state from CSV import."""
    cash_target_gbp: DecimalStr
    holdings: list[ImportTargetHolding]


class ImportBasisVersion(BaseModel):
    """Snapshot versions used to compute the import plan."""
    cash_snapshot_version: int
    holding_versions: dict[str, int]  # listing_id -> version_no


class ImportSummary(BaseModel):
    """Summary of CSV import parsing."""
    holding_rows: int
    cash_rows: int
    errors: int
    warnings: int


class ImportValidationError(BaseModel):
    """Row-level or file-level validation error."""
    row_number: int | None
    field: str | None
    message: str


class ImportValidationWarning(BaseModel):
    """Row-level or file-level validation warning."""
    row_number: int | None
    field: str | None
    message: str


class ProposedLedgerEntry(BaseModel):
    """Proposed entry generated by import delta planning."""
    entry_kind: EntryKind
    listing_id: uuid.UUID | None
    quantity_delta: DecimalStr | None
    net_cash_delta_gbp: DecimalStr
    fee_gbp: DecimalStr = "0"
    book_cost_delta_gbp: DecimalStr | None
    note: str | None


class CsvImportPreviewResponse(BaseModel):
    """Response from CSV import preview endpoint."""
    csv_profile: CsvImportProfile
    source_file_sha256: str
    portfolio_id: uuid.UUID
    portfolio_label: str
    effective_at: datetime
    basis: ImportBasisVersion
    summary: ImportSummary
    normalized_targets: ImportNormalizedTargets
    proposed_entries: list[ProposedLedgerEntry]
    warnings: list[ImportValidationWarning]
    errors: list[ImportValidationError]
    plan_hash: str


class CsvImportApplyRequest(ApiModel):
    """Request to apply a previously-previewed CSV import plan."""
    csv_profile: CsvImportProfile
    plan_hash: str
    source_file_sha256: str
    effective_at: datetime
    basis: ImportBasisVersion
    proposed_entries: list[ProposedLedgerEntry]
    idempotency_key: str | None = None


class CsvImportApplyResponse(BaseModel):
    """Response from CSV import apply endpoint."""
    batch_id: uuid.UUID
    entries_posted: int
    cash_snapshot: CashSnapshotResponse
    holding_snapshots: list[HoldingSnapshotResponse]


# ---------------------------------------------------------------------------
# List/Query Schemas
# ---------------------------------------------------------------------------

class LedgerEntryListParams(ApiModel):
    """Query parameters for listing ledger entries."""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    entry_kind: EntryKind | None = None
    listing_id: uuid.UUID | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class LedgerBatchListParams(ApiModel):
    """Query parameters for listing ledger batches."""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    source: BatchSource | None = None
