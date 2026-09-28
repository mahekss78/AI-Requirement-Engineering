import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Activity, Clock } from 'lucide-react';

export function AuditView() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAuditLogs()
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ maxWidth: '1100px', margin: '32px auto', padding: '0 24px' }}>
      <div className="glass-panel" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '700' }}>Immutable System Audit Trail</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              Full audit trail logging all state transitions, role actions, and capability events.
            </p>
          </div>
          <Activity size={24} color="#6366f1" />
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>Loading audit logs...</div>
        ) : logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>No audit logs recorded yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {logs.map((log) => (
              <div key={log.id} style={{ background: 'rgba(10, 13, 20, 0.6)', padding: '14px 18px', borderRadius: '8px', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="badge badge-analyzed" style={{ fontSize: '0.7rem' }}>{log.actor_role}</span>
                    <strong style={{ color: '#f8fafc' }}>{log.action_type}</strong>
                  </div>
                  {log.prev_state && log.new_state && (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '4px' }}>
                      State Transition: <code>{log.prev_state}</code> &rarr; <code>{log.new_state}</code>
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  <Clock size={12} />
                  {new Date(log.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
