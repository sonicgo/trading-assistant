'use client';

import { useState } from 'react';
import type {
  PolicyAllocationItem,
  PolicyAllocationResponse,
  ConstituentItem,
  Listing
} from '@/types';

interface NewConstituentRow {
  id: string;
  listing_id: string;
  sleeve_code: string;
  target_weight_pct: number;
}

// UUID validation regex
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidUUID(str: string): boolean {
  return UUID_REGEX.test(str);
}

interface TargetsFormProps {
  allocations: PolicyAllocationResponse[];
  constituents: Array<{
    listing_id: string;
    sleeve_code: string;
    is_monitored: boolean;
  }>;
  listings: Listing[];
  availableListings: Listing[]; // Listings not already in portfolio
  sleeves: Array<{
    sleeve_code: string;
    name: string;
  }>;
  onSave: (allocations: PolicyAllocationItem[]) => void;
  onAddConstituents: (constituents: ConstituentItem[], allocations: PolicyAllocationItem[]) => void;
  isPending: boolean;
}

export function TargetsForm({
  allocations,
  constituents,
  listings,
  availableListings,
  sleeves,
  onSave,
  onAddConstituents,
  isPending,
}: TargetsFormProps) {
  const [formData, setFormData] = useState<Record<string, number>>(() => {
    const initial: Record<string, number> = {};
    allocations.forEach((a) => {
      initial[a.listing_id] = a.target_weight_pct;
    });
    constituents.forEach((c) => {
      if (!(c.listing_id in initial)) {
        initial[c.listing_id] = 0;
      }
    });
    return initial;
  });

  const [selectedSleeves, setSelectedSleeves] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    allocations.forEach((a) => {
      initial[a.listing_id] = a.sleeve_code;
    });
    constituents.forEach((c) => {
      initial[c.listing_id] = c.sleeve_code;
    });
    return initial;
  });

  const [selectedTickers, setSelectedTickers] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    allocations.forEach((a) => {
      initial[a.listing_id] = a.ticker;
    });
    constituents.forEach((c) => {
      const listing = listings.find((l) => l.listing_id === c.listing_id);
      if (listing) {
        initial[c.listing_id] = listing.ticker;
      }
    });
    return initial;
  });

  // State for new rows being added
  const [newRows, setNewRows] = useState<NewConstituentRow[]>([]);
  const [error, setError] = useState('');

  const activeConstituents = constituents.filter((c) => c.is_monitored);

  const totalWeight = Object.values(formData).reduce((sum, weight) => sum + (weight || 0), 0)
    + newRows.reduce((sum, row) => sum + (row.target_weight_pct || 0), 0);

  const handleWeightChange = (listingId: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setFormData((prev) => ({ ...prev, [listingId]: numValue }));
    setError('');
  };

  const handleSleeveChange = (listingId: string, sleeveCode: string) => {
    setSelectedSleeves((prev) => ({ ...prev, [listingId]: sleeveCode }));
  };

  const handleTickerChange = (listingId: string, ticker: string) => {
    setSelectedTickers((prev) => ({ ...prev, [listingId]: ticker }));
  };

  // Handle new row changes
  const handleNewRowListingChange = (rowId: string, listingId: string) => {
    setNewRows((prev) =>
      prev.map((row) =>
        row.id === rowId ? { ...row, listing_id: listingId } : row
      )
    );
    setError('');
  };

  const handleNewRowSleeveChange = (rowId: string, sleeveCode: string) => {
    setNewRows((prev) =>
      prev.map((row) =>
        row.id === rowId ? { ...row, sleeve_code: sleeveCode } : row
      )
    );
  };

  const handleNewRowWeightChange = (rowId: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setNewRows((prev) =>
      prev.map((row) =>
        row.id === rowId ? { ...row, target_weight_pct: numValue } : row
      )
    );
    setError('');
  };

  const handleAddRow = () => {
    if (availableListings.length === 0) {
      setError('No available listings to add. All listings are already in your portfolio.');
      return;
    }
    const newRow: NewConstituentRow = {
      id: `new-${Date.now()}`,
      listing_id: availableListings[0]?.listing_id || '',
      sleeve_code: sleeves[0]?.sleeve_code || 'CORE',
      target_weight_pct: 0,
    };
    setNewRows((prev) => [...prev, newRow]);
    setError('');
  };

  const handleRemoveRow = (rowId: string) => {
    setNewRows((prev) => prev.filter((row) => row.id !== rowId));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (totalWeight > 100) {
      setError(`Total weight (${totalWeight.toFixed(1)}%) exceeds 100%`);
      return;
    }

    const existingListingIds = Object.keys(formData).filter(isValidUUID);
    const validNewRows = newRows.filter((row) => isValidUUID(row.listing_id));
    const newRowListingIds = validNewRows.map((row) => row.listing_id);
    const allListingIds = [...existingListingIds, ...newRowListingIds];

    if (allListingIds.length === 0) {
      setError('No allocations to save.');
      return;
    }

    const existingConstituents: ConstituentItem[] = existingListingIds.map((listingId) => ({
      listing_id: listingId,
      sleeve_code: selectedSleeves[listingId] || 'CORE',
      is_monitored: true,
    }));
    
    const newConstituents: ConstituentItem[] = validNewRows.map((row) => ({
      listing_id: row.listing_id,
      sleeve_code: row.sleeve_code || 'CORE',
      is_monitored: true,
    }));
    
    const allConstituents: ConstituentItem[] = [...existingConstituents, ...newConstituents];

    const existingAllocations: PolicyAllocationItem[] = existingListingIds
      .filter((listingId) => formData[listingId] > 0)
      .map((listingId) => {
        const listing = listings.find((l) => l.listing_id === listingId);
        return {
          listing_id: listingId,
          ticker: selectedTickers[listingId] || listing?.ticker || '',
          sleeve_code: selectedSleeves[listingId] || 'CORE',
          target_weight_pct: formData[listingId] || 0,
          policy_role: 'INVESTED_ASSET',
        };
      });
    
    const newAllocations: PolicyAllocationItem[] = validNewRows
      .filter((row) => row.target_weight_pct > 0)
      .map((row) => {
        const listing = listings.find((l) => l.listing_id === row.listing_id);
        return {
          listing_id: row.listing_id,
          ticker: listing?.ticker || '',
          sleeve_code: row.sleeve_code || 'CORE',
          target_weight_pct: row.target_weight_pct || 0,
          policy_role: 'INVESTED_ASSET',
        };
      });
    
    const allAllocations: PolicyAllocationItem[] = [...existingAllocations, ...newAllocations];

    if (allAllocations.length === 0) {
      setError('Please enter target weights for at least one listing.');
      return;
    }

    onAddConstituents(allConstituents, allAllocations);
  };

  // Get available listings for a specific row (excluding already-selected ones)
  const getAvailableListingsForRow = (rowId: string) => {
    const selectedInOtherRows = newRows
      .filter((row) => row.id !== rowId)
      .map((row) => row.listing_id);
    return availableListings.filter(
      (listing) => !selectedInOtherRows.includes(listing.listing_id)
    );
  };

  const hasExistingData = Object.keys(formData).length > 0;
  const hasNewRows = newRows.length > 0;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="p-4 bg-red-50 text-red-600 rounded-xl border border-red-100">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 bg-gray-50 border-b border-gray-200">
          <div className="grid grid-cols-12 gap-4 text-sm font-semibold text-gray-600">
            <div className="col-span-3">Listing</div>
            <div className="col-span-3">Ticker</div>
            <div className="col-span-3">Sleeve</div>
            <div className="col-span-2">Target Weight %</div>
            <div className="col-span-1"></div>
          </div>
        </div>

        <div className="divide-y divide-gray-100">
          {/* Existing Allocations - render based on formData keys */}
          {Object.keys(formData).length === 0 && newRows.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <p className="mb-4">No active constituents in this portfolio.</p>
              <p className="text-sm text-gray-400">
                Click &quot;+ Add Listing&quot; below to add listings from the registry.
              </p>
            </div>
          ) : (
            Object.keys(formData).map((listingId) => {
              const listing = listings.find((l) => l.listing_id === listingId);
              const weight = formData[listingId] || 0;

              return (
                <div key={listingId} className="p-4">
                  <div className="grid grid-cols-12 gap-4 items-center">
                    <div className="col-span-3">
                      <p className="font-semibold text-gray-900">
                        {listing?.ticker || selectedTickers[listingId] || 'Unknown'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {listing?.exchange || ''}
                      </p>
                    </div>

                    <div className="col-span-3">
                      <input
                        type="text"
                        value={selectedTickers[listingId] || listing?.ticker || ''}
                        onChange={(e) =>
                          handleTickerChange(listingId, e.target.value)
                        }
                        className="w-full p-2 border rounded-lg text-sm"
                        placeholder="Ticker"
                      />
                    </div>

                    <div className="col-span-3">
                      <select
                        value={selectedSleeves[listingId] || 'CORE'}
                        onChange={(e) =>
                          handleSleeveChange(listingId, e.target.value)
                        }
                        className="w-full p-2 border rounded-lg text-sm"
                      >
                        {sleeves.map((sleeve) => (
                          <option key={sleeve.sleeve_code} value={sleeve.sleeve_code}>
                            {sleeve.sleeve_code}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="col-span-2">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        value={weight || ''}
                        onChange={(e) =>
                          handleWeightChange(listingId, e.target.value)
                        }
                        className="w-full p-2 border rounded-lg text-sm"
                        placeholder="0.00"
                      />
                    </div>

                    <div className="col-span-1"></div>
                  </div>
                </div>
              );
            })
          )}

          {/* New Constituent Rows */}
          {newRows.map((row) => {
            const availableForThisRow = getAvailableListingsForRow(row.id);
            const selectedListing = availableListings.find(
              (l) => l.listing_id === row.listing_id
            );

            return (
              <div key={row.id} className="p-4 bg-blue-50">
                <div className="grid grid-cols-12 gap-4 items-center">
                  <div className="col-span-3">
                    <select
                      value={row.listing_id}
                      onChange={(e) => handleNewRowListingChange(row.id, e.target.value)}
                      className="w-full p-2 border rounded-lg text-sm bg-white"
                    >
                      <option value="">Select listing...</option>
                      {availableForThisRow.map((listing) => (
                        <option key={listing.listing_id} value={listing.listing_id}>
                          {listing.ticker}
                        </option>
                      ))}
                    </select>
                    {selectedListing && (
                      <p className="text-xs text-gray-500 mt-1">
                        {selectedListing.exchange} • {selectedListing.trading_currency}
                      </p>
                    )}
                  </div>

                  <div className="col-span-3">
                    <input
                      type="text"
                      value={selectedListing?.ticker || ''}
                      disabled
                      className="w-full p-2 border rounded-lg text-sm bg-gray-100 text-gray-500"
                      placeholder="Auto-filled"
                    />
                  </div>

                  <div className="col-span-3">
                    <select
                      value={row.sleeve_code}
                      onChange={(e) => handleNewRowSleeveChange(row.id, e.target.value)}
                      className="w-full p-2 border rounded-lg text-sm bg-white"
                    >
                      {sleeves.map((sleeve) => (
                        <option key={sleeve.sleeve_code} value={sleeve.sleeve_code}>
                          {sleeve.sleeve_code} - {sleeve.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-span-2">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      value={row.target_weight_pct || ''}
                      onChange={(e) => handleNewRowWeightChange(row.id, e.target.value)}
                      className="w-full p-2 border rounded-lg text-sm bg-white"
                      placeholder="0.00"
                    />
                  </div>

                  <div className="col-span-1">
                    <button
                      type="button"
                      onClick={() => handleRemoveRow(row.id)}
                      className="text-red-500 hover:text-red-700 text-sm"
                      title="Remove"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Add Listing Button */}
      <div className="flex justify-start">
        <button
          type="button"
          onClick={handleAddRow}
          disabled={availableListings.length === 0}
          className="px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          + Add Listing
        </button>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm">
          <span className="text-gray-600">Total Target Weight: </span>
          <span
            className={`font-bold ${
              totalWeight > 100 ? 'text-red-600' : totalWeight === 100 ? 'text-green-600' : 'text-blue-600'
            }`}
          >
            {totalWeight.toFixed(1)}%
          </span>
          {totalWeight > 100 && (
            <span className="text-red-500 text-xs ml-2">(Exceeds 100%)</span>
          )}
          {totalWeight < 100 && (
            <span className="text-gray-400 text-xs ml-2">({(100 - totalWeight).toFixed(1)}% unallocated)</span>
          )}
        </div>

        <button
          type="submit"
          disabled={isPending || totalWeight > 100 || (!hasExistingData && !hasNewRows)}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isPending ? 'Saving...' : 'Save Targets'}
        </button>
      </div>
    </form>
  );
}
