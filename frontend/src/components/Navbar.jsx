import React from 'react';
import { Shield, LayoutDashboard, FileUp, Bell, Activity, LogOut, User } from 'lucide-react';

export function Navbar({ currentUser, activeTab, setActiveTab, unreadNotificationsCount, onLogout }) {
  const role = currentUser?.assigned_role || 'NO_ROLE';

  const roleColors = {
    BUSINESS_ANALYST: '#818cf8',
    CLIENT: '#f472b6',
    DEVELOPER: '#38bdf8',
    QA: '#c084fc',
    PRODUCT_OWNER: '#34d399',
  };

  return (
    <header style={{
      background: 'rgba(18, 22, 36, 0.8)',
      backdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--border-subtle)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '0 24px',
    }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto', height: '68px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => setActiveTab('dashboard')}>
          <div style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)', padding: '8px', borderRadius: '10px', display: 'flex' }}>
            <Shield size={22} color="white" />
          </div>
          <div>
            <div style={{ fontWeight: '700', fontSize: '1.15rem', letterSpacing: '-0.02em', lineHeight: 1.2 }}>AREA Platform</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Automated Requirements Engineering</div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '6px' }}>
          {[
            { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { id: 'ingest', label: 'Ingest Document', icon: FileUp },
            { id: 'notifications', label: 'Notifications', icon: Bell, badge: unreadNotificationsCount },
            { id: 'audit', label: 'Audit Trail', icon: Activity },
          ].map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                  color: isActive ? '#818cf8' : 'var(--text-secondary)',
                  fontWeight: isActive ? '600' : '400',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative',
                }}
              >
                <Icon size={16} />
                <span>{item.label}</span>
                {item.badge > 0 && (
                  <span style={{
                    background: '#ef4444',
                    color: 'white',
                    fontSize: '0.65rem',
                    fontWeight: '700',
                    padding: '2px 6px',
                    borderRadius: '999px',
                    lineHeight: 1,
                  }}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* User Profile & Role */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 12px', background: 'rgba(255, 255, 255, 0.04)', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
            <User size={16} color="var(--text-muted)" />
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: '500' }}>{currentUser?.email}</div>
              <div style={{ fontSize: '0.65rem', fontWeight: '700', color: roleColors[role] || 'var(--text-muted)' }}>
                {role.replace('_', ' ')}
              </div>
            </div>
          </div>

          <button
            onClick={onLogout}
            title="Sign Out"
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              color: '#f87171',
              padding: '8px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}
