'use client';

import type { RecentActivityItem } from '@/types';

interface ActivityFeedProps {
  activities: RecentActivityItem[];
}

export function ActivityFeed({ activities }: ActivityFeedProps) {
  const getActivityIcon = (type: string) => {
    const icons: Record<string, string> = {
      'Recommendation Executed': '✅',
      'Recommendation Ignored': '❌',
      'Ledger Import': '📥',
      'Prices Synced': '💰',
      'Portfolio Loaded': '👁️',
    };
    return icons[type] || '📝';
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
        <p className="text-sm text-gray-500 mt-1">
          Latest actions on this portfolio
        </p>
      </div>

      <div className="divide-y divide-gray-100">
        {activities.map((activity, index) => (
          <div key={index} className="p-4 hover:bg-gray-50 flex items-start gap-3">
            <div className="text-xl">{getActivityIcon(activity.activity_type)}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-900">
                {activity.activity_type}
              </p>
              <p className="text-sm text-gray-600 truncate">
                {activity.description}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {formatTime(activity.occurred_at)}
                {activity.actor_name && ` • by ${activity.actor_name}`}
              </p>
            </div>
          </div>
        ))}
        {activities.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            No recent activity
          </div>
        )}
      </div>
    </div>
  );
}
