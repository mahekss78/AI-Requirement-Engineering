import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { FileText, ShieldAlert, CheckCircle2, AlertTriangle, TrendingUp, ChevronRight, RefreshCw } from 'lucide-react';

export function DashboardView({ onSelectRequirement, onNavigateIngest }) {
  const [metrics, setMetrics] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [mRes, rRes] = await Promise.all([
        api.getDashboardMetrics().catch(() => null),
        api.getRequirements().catch(() => []),
      ]);
      setMetrics(mRes);
      setRequirements(rRes);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getStateBadgeClass = (state) => {
    switch (state) {
      case 'DRAFT': return 'badge-draft';
      case 'INGESTING': return 'badge-ingesting';
      case 'AI_ANALYZED': return 'badge-analyzed';
      case 'BA_REVIEW': return 'badge-ba-review';
      case 'CLARIFYING': return 'badge-clarifying';
      case 'PEER_REVIEW': return 'badge-peer-review';
      case 'APPROVED': return 'badge-approved';
      case 'JIRA_SYNCED': return 'badge-jira-synced';
      case 'FROZEN': return 'badge-frozen';
      case 'FAILED': return 'badge-failed';
      default: return 'badge-draft';
    }
  };

  const getHealthBadge = (status) => {
    switch (status) {
      case 'Healthy':
        return <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(52, 211, 153, 0.3)' }}><CheckCircle2 size={12} /> Healthy</span>;
      case 'Needs Review':
        return <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(251, 191, 36, 0.3)' }}><AlertTriangle size={12} /> Needs Review</span>;
      case 'At Risk':
        return <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(248, 113, 113, 0.3)' }}><ShieldAlert size={12} /> At Risk</span>;
      case 'Blocked':
        return <span className="badge" style={{ background: 'rgba(225, 29, 72, 0.2)', color: '#fda4af', border: '1px solid rgba(244, 63, 94, 0.4)' }}><ShieldAlert size={12} /> Blocked</span>;
      default:
        return <span className="badge badge-draft">{status}</span>;
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '32px auto', padding: '0 24px' }}>
      
      {/* Top Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '700', letterSpacing: '-0.02em' }}>Requirements Overview</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '4px' }}>
            Real-time automated scoring, quality metrics, and 10-state lifecycle progression.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-secondary" onClick={fetchData} title="Refresh Dashboard">
            <RefreshCw size={16} /> Refresh
          </button>
          <button className="btn btn-primary" onClick={onNavigateIngest}>
            + Ingest New Document
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '14px', borderRadius: '10px', marginBottom: '24px' }}>
          {error}
        </div>
      )}

      {/* Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        {[
          { label: 'Total Requirements', value: metrics?.total_requirements ?? requirements.length, icon: FileText, color: '#6366f1' },
          { label: 'Frozen Requirements', value: metrics?.frozen_count ?? requirements.filter(r => r.current_state === 'FROZEN').length, icon: CheckCircle2, color: '#10b981' },
          { label: 'At Risk', value: metrics?.at_risk_count ?? requirements.filter(r => r.health_status === 'At Risk').length, icon: AlertTriangle, color: '#f59e0b' },
          { label: 'Blocked', value: metrics?.blocked_count ?? requirements.filter(r => r.health_status === 'Blocked').length, icon: ShieldAlert, color: '#ef4444' },
          { label: 'Avg Confidence Score', value: `${(metrics?.average_confidence ?? 85.0).toFixed(1)}%`, icon: TrendingUp, color: '#06b6d4' },
          { label: 'Avg Health Score', value: `${(metrics?.average_health ?? 90.0).toFixed(1)}%`, icon: CheckCircle2, color: '#8b5cf6' },
        ].map((m, idx) => {
          const Icon = m.icon;
          return (
            <div key={idx} className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{m.label}</span>
                <div style={{ background: `${m.color}20`, padding: '8px', borderRadius: '8px', display: 'flex' }}>
                  <Icon size={18} color={m.color} />
                </div>
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '700' }}>{m.value}</div>
            </div>
          );
        })}
      </div>

      {/* Requirements Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: '600' }}>Active Requirements Pipeline</h2>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{requirements.length} item(s)</span>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading requirements...</div>
        ) : requirements.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No requirements ingested yet. Click "+ Ingest New Document" above to run the 6-step AI Capability Pipeline.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Requirement Title</th>
                  <th style={{ padding: '12px 16px' }}>State</th>
                  <th style={{ padding: '12px 16px' }}>Health Status</th>
                  <th style={{ padding: '12px 16px' }}>Confidence Score</th>
                  <th style={{ padding: '12px 16px' }}>Assigned Owner</th>
                  <th style={{ padding: '12px 16px' }}>Ver.</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map((req) => (
                  <tr
                    key={req.id}
                    onClick={() => onSelectRequirement(req.id)}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '16px', fontWeight: '500', color: '#f8fafc' }}>
                      {req.title}
                    </td>
                    <td style={{ padding: '16px' }}>
                      <span className={`badge ${getStateBadgeClass(req.current_state)}`}>
                        {req.current_state}
                      </span>
                    </td>
                    <td style={{ padding: '16px' }}>
                      {getHealthBadge(req.health_status)}
                    </td>
                    <td style={{ padding: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '80px', height: '6px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: `${req.confidence_score}%`, height: '100%', background: req.confidence_score >= 80 ? '#10b981' : req.confidence_score >= 60 ? '#f59e0b' : '#ef4444' }} />
                        </div>
                        <span style={{ fontWeight: '600', fontSize: '0.8rem' }}>{req.confidence_score?.toFixed(1)}%</span>
                      </div>
                    </td>
                    <td style={{ padding: '16px', color: 'var(--text-secondary)' }}>
                      {req.assigned_role}
                    </td>
                    <td style={{ padding: '16px', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      v{req.version}
                    </td>
                    <td style={{ padding: '16px', textAlign: 'right' }}>
                      <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>
                        View Detail <ChevronRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
