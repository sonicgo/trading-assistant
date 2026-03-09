'use client';

import { useRef, useEffect, useState } from 'react';
import { useNotifications } from '@/hooks/use-notifications';
import type { Notification } from '@/types';

/**
 * NotificationsDropdown Component
 * 
 * Displays a bell icon with unread count badge and a dropdown showing notifications.
 * Polls for new notifications every 30 seconds via the useNotifications hook.
 * 
 * Features:
 * - Bell icon with red badge showing unread count
 * - Click to toggle dropdown visibility
 * - Notification list with severity indicator, title, body preview, and timestamp
 * - Click outside to close dropdown
 * - Empty state message
 */
export function NotificationsDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  // Fetch notifications with 30-second polling
  const { data: notifications = [], isLoading } = useNotifications();
  
  // Calculate unread count
  const unreadCount = notifications.filter(n => !n.read_at).length;
  
  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);
  
  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };
  
  /**
   * Get severity indicator color
   */
  const getSeverityColor = (severity: string): string => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-red-500';
      case 'WARN':
        return 'bg-amber-500';
      case 'INFO':
      default:
        return 'bg-blue-500';
    }
  };
  
  /**
   * Format timestamp to relative time (e.g., "2 minutes ago")
   */
  const formatTime = (timestamp: string): string => {
    const now = new Date();
    const created = new Date(timestamp);
    const diffMs = now.getTime() - created.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return created.toLocaleDateString();
  };
  
  /**
   * Truncate text to max length
   */
  const truncateText = (text: string | null, maxLength: number = 60): string => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };
  
  return (
    <div ref={dropdownRef} className="relative">
      {/* Bell Icon Button */}
      <button
        onClick={toggleDropdown}
        className="relative p-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        aria-label="Notifications"
        aria-expanded={isOpen}
      >
        {/* Bell Icon */}
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        
        {/* Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>
      
      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-gray-200 z-50">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
          </div>
          
          {/* Notifications List */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                Loading notifications...
              </div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No notifications
              </div>
            ) : (
              <ul className="divide-y divide-gray-100">
                {notifications.map((notification: Notification) => (
                  <li
                    key={notification.notification_id}
                    className="px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex gap-3">
                      {/* Severity Indicator Dot */}
                      <div className="flex-shrink-0 mt-1">
                        <div
                          className={`w-2 h-2 rounded-full ${getSeverityColor(
                            notification.severity
                          )}`}
                        />
                      </div>
                      
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        {/* Title */}
                        <p className="text-sm font-semibold text-gray-900 truncate">
                          {notification.title}
                        </p>
                        
                        {/* Body Preview */}
                        {notification.body && (
                          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                            {truncateText(notification.body, 80)}
                          </p>
                        )}
                        
                        {/* Timestamp */}
                        <p className="text-xs text-gray-400 mt-1">
                          {formatTime(notification.created_at)}
                        </p>
                      </div>
                      
                      {/* Unread Indicator */}
                      {!notification.read_at && (
                        <div className="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2" />
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
