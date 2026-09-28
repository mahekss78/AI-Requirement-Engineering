import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Bell, Check, Info, AlertTriangle, MessageSquare } from 'lucide-react';

export function NotificationsView({ currentUser }) {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await api.getNotifications();
      setNotifications(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleMarkRead = async (id) => {
    try {
      await api.markNotificationRead(id);
      fetchNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ maxWidth: '900px', margin: '32px auto', padding: '0 24px' }}>
      <div className="glass-panel" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '700' }}>In-App Role Notifications</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              Notifications for assigned role: <strong>{currentUser?.assigned_role}</strong>
            </p>
          </div>
          <Bell size={24} color="#6366f1" />
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>Loading notifications...</div>
        ) : notifications.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>No notifications for your role.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {notifications.map((n) => (
              <div
                key={n.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px',
                  borderRadius: '10px',
                  background: n.is_read ? 'rgba(255, 255, 255, 0.02)' : 'rgba(99, 102, 241, 0.08)',
                  border: n.is_read ? '1px solid var(--border-subtle)' : '1px solid rgba(99, 102, 241, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {n.notification_type === 'WARNING' ? (
                    <AlertTriangle size={20} color="#f59e0b" />
                  ) : n.notification_type === 'REVIEW_REQUEST' ? (
                    <MessageSquare size={20} color="#c084fc" />
                  ) : (
                    <Info size={20} color="#38bdf8" />
                  )}
                  <div>
                    <div style={{ fontSize: '0.9rem', fontWeight: n.is_read ? '400' : '600' }}>{n.message}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {new Date(n.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                {!n.is_read && (
                  <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }} onClick={() => handleMarkRead(n.id)}>
                    <Check size={14} /> Mark Read
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
