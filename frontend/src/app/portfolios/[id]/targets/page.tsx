'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { usePolicyAllocations, useUpdatePolicyAllocations } from '@/hooks/use-policy-allocations';
import { useConstituents, useBulkUpsertConstituents } from '@/hooks/use-constituents';
import { useListings } from '@/hooks/use-listings';
import { useSleeves } from '@/hooks/use-sleeves';
import { TargetsForm } from '@/components/portfolio/targets-form';
import type { PolicyAllocationItem, ConstituentItem } from '@/types';

export default function TargetsPage() {
  const { id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;
  const { user, isLoading: authLoading } = useAuth();
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  const { data: allocations, isLoading: allocationsLoading } = usePolicyAllocations(portfolioId);
  const { data: constituents, isLoading: constituentsLoading } = useConstituents(portfolioId);
  const { data: listings } = useListings({ limit: 200 });
  const { data: sleeves } = useSleeves();
  const updateAllocations = useUpdatePolicyAllocations(portfolioId);
  const upsertConstituents = useBulkUpsertConstituents(portfolioId);

  // Calculate available listings (not already in portfolio)
  const portfolioListingIds = new Set(constituents?.map((c) => c.listing_id) || []);
  const availableListings = listings?.items.filter(
    (listing) => !portfolioListingIds.has(listing.listing_id)
  ) || [];

  const handleSave = (allocationData: PolicyAllocationItem[]) => {
    setSuccessMessage('');
    updateAllocations.mutate(
      { allocations: allocationData },
      {
        onSuccess: () => {
          setSuccessMessage('Targets saved successfully!');
          setTimeout(() => setSuccessMessage(''), 3000);
        },
      }
    );
  };

  const handleAddConstituents = (
    newConstituents: ConstituentItem[],
    allAllocations: PolicyAllocationItem[]
  ) => {
    setSuccessMessage('');
    
    // Step 1: Create the constituents first
    upsertConstituents.mutate(newConstituents, {
      onSuccess: () => {
        // Step 2: After constituents are created, save the allocations
        updateAllocations.mutate(
          { allocations: allAllocations },
          {
            onSuccess: () => {
              setSuccessMessage('Listings added and targets saved successfully!');
              setTimeout(() => setSuccessMessage(''), 3000);
            },
            onError: (error: any) => {
              setSuccessMessage(`Error saving targets: ${error.message || 'Unknown error'}`);
            },
          }
        );
      },
      onError: (error: any) => {
        setSuccessMessage(`Error adding listings: ${error.message || 'Unknown error'}`);
      },
    });
  };

  if (allocationsLoading || constituentsLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded-xl"></div>
        </div>
      </div>
    );
  }

  const isPending = updateAllocations.isPending || upsertConstituents.isPending;
  const error = updateAllocations.error || upsertConstituents.error;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => router.push(`/portfolios/${portfolioId}`)}
          className="text-sm text-blue-600 hover:underline mb-4 flex items-center gap-1"
        >
          ← Back to Portfolio
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Manifesto Targets</h1>
        <p className="text-gray-600 mt-1">
          Set your target allocation weights for each sleeve. The engine will use these to calculate drift and generate trade recommendations.
        </p>
      </div>

      {successMessage && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-xl border border-green-200">
          ✓ {successMessage}
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-50 text-red-600 rounded-xl border border-red-100">
          Error: {error instanceof Error ? error.message : 'An error occurred. Please try again.'}
        </div>
      )}

      <TargetsForm
        allocations={allocations || []}
        constituents={constituents || []}
        listings={listings?.items || []}
        availableListings={availableListings}
        sleeves={sleeves || []}
        onSave={handleSave}
        onAddConstituents={handleAddConstituents}
        isPending={isPending}
      />
    </div>
  );
}
