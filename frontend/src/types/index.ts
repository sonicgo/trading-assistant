/**
 * Trading Assistant Frontend Types
 * Derived from backend Pydantic schemas
 */

// ============================================================================
// Common
// ============================================================================

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
  total: number;
}

// ============================================================================
// Portfolio Types
// ============================================================================

export type TaxProfile = 'SIPP' | 'ISA' | 'GIA';

export interface Portfolio {
  portfolio_id: string;
  owner_user_id: string;
  name: string;
  base_currency: string;
  tax_profile: TaxProfile;
  broker: string;
  is_enabled: boolean;
  created_at: string;
}

export interface PortfolioCreate {
  name: string;
  base_currency?: string;
  tax_profile: TaxProfile;
  broker?: string;
}

export interface PortfolioUpdate {
  name?: string;
  base_currency?: string;
  tax_profile?: TaxProfile;
  broker?: string;
  is_enabled?: boolean;
}

// ============================================================================
// Constituent Types
// ============================================================================

export interface Constituent {
  portfolio_id: string;
  listing_id: string;
  sleeve_code: string;
  is_monitored: boolean;
  created_at: string;
}

export interface ConstituentItem {
  listing_id: string;
  sleeve_code: string;
  is_monitored: boolean;
}

export interface ConstituentBulkUpsert {
  items: ConstituentItem[];
  replace_missing: boolean;
}

export interface ConstituentBulkUpsertResponse {
  status: string;
  updated_count: number;
}

// ============================================================================
// Sleeve Types (Reference Data)
// ============================================================================

export interface Sleeve {
  sleeve_code: string;
  name: string;
}

/** Hardcoded sleeve values from DB seed migration */
export const SLEEVES: Sleeve[] = [
  { sleeve_code: 'CORE', name: 'Core Passive' },
  { sleeve_code: 'SATELLITE', name: 'Satellite Alpha' },
  { sleeve_code: 'CASH', name: 'Cash Buffer' },
  { sleeve_code: 'GROWTH_SEMIS', name: 'Growth - Semiconductors' },
  { sleeve_code: 'ENERGY', name: 'Thematic - Energy Transition' },
  { sleeve_code: 'HEALTHCARE', name: 'Thematic - Healthcare Innovation' },
];

// ============================================================================
// Registry - Instrument Types
// ============================================================================

export type InstrumentType = 'ETF' | 'STOCK' | 'ETC' | 'FUND' | 'OTHER';

export interface Instrument {
  instrument_id: string;
  isin: string;
  name: string | null;
  instrument_type: InstrumentType;
  created_at: string;
}

export interface InstrumentCreate {
  isin: string;
  name: string;
  instrument_type: InstrumentType;
}

export interface InstrumentUpdate {
  name?: string;
  instrument_type?: InstrumentType;
}

export type InstrumentsPage = Page<Instrument>;

// ============================================================================
// Registry - Listing Types
// ============================================================================

export type PriceScale = 'MAJOR' | 'MINOR';

export interface Listing {
  listing_id: string;
  instrument_id: string;
  ticker: string;
  exchange: string;
  trading_currency: string;
  price_scale: PriceScale;
  is_primary: boolean;
  created_at: string;
}

export interface ListingCreate {
  instrument_id: string;
  ticker: string;
  exchange: string;
  trading_currency: string;
  price_scale: PriceScale;
  is_primary?: boolean;
}

export interface ListingUpdate {
  ticker?: string;
  exchange?: string;
  trading_currency?: string;
  price_scale?: PriceScale;
  is_primary?: boolean;
}

export type ListingsPage = Page<Listing>;

// ============================================================================
// Auth Types
// ============================================================================

export interface User {
  user_id: string;
  email: string;
  is_enabled: boolean;
  is_bootstrap_admin: boolean;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

// ============================================================================
// Market Data Types
// ============================================================================

export interface PricePoint {
  price_point_id: string;
  listing_id: string;
  as_of: string;
  price: string;           // DecimalStr from backend
  currency: string | null;
  is_close: boolean;
  source_id: string;
  created_at: string;
}

export interface FxRate {
  fx_rate_id: string;
  base_ccy: string;
  quote_ccy: string;
  as_of: string;
  rate: string;            // DecimalStr from backend
  source_id: string;
  created_at: string;
}

export interface RefreshResult {
  job_id: string;
  status: string;
}

export interface SyncResult {
  portfolio_id: string;
  total_listings: number;
  prices_fetched: number;
  prices_inserted: number;
  errors: string[];
  status: string;
}

// ============================================================================
// Alert Types
// ============================================================================

export type AlertSeverity = 'INFO' | 'WARN' | 'CRITICAL';

export interface Alert {
  alert_id: string;
  portfolio_id: string;
  listing_id: string | null;
  severity: AlertSeverity;
  rule_code: string;
  title: string;
  message: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
}

// ============================================================================
// Freeze Types
// ============================================================================

export interface FreezeState {
  freeze_id: string;
  portfolio_id: string;
  is_frozen: boolean;
  reason_alert_id: string | null;
  created_at: string;
  cleared_at: string | null;
  cleared_by_user_id: string | null;
}

export interface FreezeStatus {
  is_frozen: boolean;
  freeze: FreezeState | null;
}

// ============================================================================
// Notification Types
// ============================================================================

export interface Notification {
  notification_id: string;
  owner_user_id: string;
  severity: string;
  title: string;
  body: string | null;
  created_at: string;
  read_at: string | null;
  meta: Record<string, unknown> | null;
}

// ============================================================================
// Ledger Types (Phase 3)
// ============================================================================

export type EntryKind = 'CONTRIBUTION' | 'BUY' | 'SELL' | 'ADJUSTMENT' | 'REVERSAL';
export type BatchSource = 'UI' | 'CSV_IMPORT' | 'REVERSAL';
export type CsvImportProfile = 'positions_gbp_v1';

export interface LedgerEntry {
  entry_id: string;
  batch_id: string;
  portfolio_id: string;
  entry_kind: EntryKind;
  effective_at: string;
  listing_id: string | null;
  quantity_delta: string | null;
  net_cash_delta_gbp: string;
  fee_gbp: string | null;
  book_cost_delta_gbp: string | null;
  reversal_of_entry_id: string | null;
  created_at: string;
  note: string | null;
  meta: Record<string, unknown> | null;
}

export interface LedgerBatch {
  batch_id: string;
  portfolio_id: string;
  submitted_by_user_id: string;
  source: BatchSource;
  created_at: string;
  note: string | null;
  meta: Record<string, unknown> | null;
  idempotency_key: string | null;
  entries: LedgerEntry[];
}

export interface LedgerEntryCreate {
  entry_id?: string;
  entry_kind: EntryKind;
  effective_at: string;
  listing_id?: string;
  quantity_delta?: string;
  net_cash_delta_gbp: string;
  fee_gbp?: string;
  book_cost_delta_gbp?: string;
  note?: string;
  meta?: Record<string, unknown>;
}

export interface LedgerBatchCreate {
  batch_id?: string;
  idempotency_key?: string;
  entries: LedgerEntryCreate[];
  note?: string;
  meta?: Record<string, unknown>;
}

export interface LedgerReversalRequest {
  batch_id?: string;
  idempotency_key?: string;
  entry_ids: string[];
  note?: string;
}

export interface CashSnapshot {
  portfolio_id: string;
  balance_gbp: string;
  updated_at: string;
  last_entry_id: string | null;
  version_no: number;
}

export interface HoldingSnapshot {
  portfolio_id: string;
  listing_id: string;
  quantity: string;
  book_cost_gbp: string;
  avg_cost_gbp: string;
  updated_at: string;
  last_entry_id: string | null;
  version_no: number;
}

export interface HoldingSnapshotList {
  portfolio_id: string;
  holdings: HoldingSnapshot[];
  total_book_cost_gbp: string;
}

export interface ImportTargetHolding {
  ticker: string;
  listing_id: string;
  target_quantity: string;
  target_book_cost_gbp: string;
  investment_name: string;
}

export interface ImportBasisVersion {
  cash_snapshot_version: number;
  holding_versions: Record<string, number>;
}

export interface ImportSummary {
  holding_rows: number;
  cash_rows: number;
  errors: number;
  warnings: number;
}

export interface ImportValidationError {
  row_number: number | null;
  field: string | null;
  message: string;
}

export interface ImportValidationWarning {
  row_number: number | null;
  field: string | null;
  message: string;
}

export interface ProposedLedgerEntry {
  entry_kind: EntryKind;
  listing_id: string | null;
  quantity_delta: string | null;
  net_cash_delta_gbp: string;
  fee_gbp: string;
  book_cost_delta_gbp: string | null;
  note: string | null;
}

export interface CsvImportPreviewRequest {
  csv_profile: CsvImportProfile;
  idempotency_key?: string;
  file_content_base64: string;
}

export interface CsvImportPreviewResponse {
  csv_profile: CsvImportProfile;
  source_file_sha256: string;
  portfolio_id: string;
  portfolio_label: string;
  effective_at: string;
  basis: ImportBasisVersion;
  summary: ImportSummary;
  normalized_targets: {
    cash_target_gbp: string;
    holdings: ImportTargetHolding[];
  };
  proposed_entries: ProposedLedgerEntry[];
  warnings: ImportValidationWarning[];
  errors: ImportValidationError[];
  plan_hash: string;
}

export interface CsvImportApplyRequest {
  csv_profile: CsvImportProfile;
  plan_hash: string;
  source_file_sha256: string;
  effective_at: string;
  basis: ImportBasisVersion;
  proposed_entries: ProposedLedgerEntry[];
  idempotency_key?: string;
}

export interface CsvImportApplyResponse {
  batch_id: string;
  entries_posted: number;
  cash_snapshot: CashSnapshot;
  holding_snapshots: HoldingSnapshot[];
}

export type LedgerBatchesPage = Page<LedgerBatch>;
export type LedgerEntriesPage = Page<LedgerEntry>;

// ============================================================================
// Engine Types (Phase 4 - Calculation Engine)
// ============================================================================

export interface CurrentPosition {
  listing_id: string;
  ticker: string;
  current_quantity: string;
  current_price_gbp: string;
  current_value_gbp: string;
  target_weight_pct: string;
  current_weight_pct: string;
  drift_pct: string;
  is_drifted: boolean;
}

export interface ProposedTrade {
  action: 'BUY' | 'SELL';
  ticker: string;
  listing_id: string;
  quantity: string;
  estimated_value_gbp: string;
  reason: string;
}

export interface TradePlanResponse {
  portfolio_id: string;
  as_of: string;
  total_value_gbp: string;
  cash_balance_gbp: string;
  positions: CurrentPosition[];
  trades: ProposedTrade[];
  projected_post_trade_cash: string;
  cash_pool_used: string;
  cash_pool_remaining: string;
  warnings: string[];
  is_blocked: boolean;
  block_reason: string | null;
  block_message: string | null;
}
