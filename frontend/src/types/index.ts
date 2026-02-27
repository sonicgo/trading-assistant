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
