import React, { useEffect, useState } from 'react';
import { api } from './services/api';
import { LoginView } from './components/LoginView';
import { Navbar } from './components/Navbar';
import { DashboardView } from './components/DashboardView';
import { IngestionView } from './components/IngestionView';
import { RequirementDetailView } from './components/RequirementDetailView';
import { NotificationsView } from './components/NotificationsView';
import { AuditView } from './components/AuditView';

export function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedReqId, setSelectedReqId] = useState(null);
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState(0);

  // Check server session on startup
  const checkSession = async () => {
    setLoading(true);
    try {
      const sessionData = await api.getSession();
      if (sessionData && sessionData.authenticated) {
        setCurrentUser(sessionData);
      } else {
        setCurrentUser(null);
      }
    } catch (err) {
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  // Poll unread notifications count when logged in
  useEffect(() => {
    if (!currentUser || !currentUser.authenticated || !currentUser.assigned_role) return;
    const fetchNotifs = async () => {
      try {
        const notifs = await api.getNotifications();
        const unread = notifs.filter(n => !n.is_read).length;
        setUnreadNotificationsCount(unread);
      } catch (err) {
        // Silent catch
      }
    };
    fetchNotifs();
    const interval = setInterval(fetchNotifs, 10000);
    return () => clearInterval(interval);
  }, [currentUser]);

  const handleLoginSuccess = (userData) => {
    setCurrentUser(userData);
    setActiveTab('dashboard');
  };

  const handleLogout = async () => {
    await api.logout();
    setCurrentUser(null);
    setSelectedReqId(null);
  };

  const handleSelectRequirement = (id) => {
    setSelectedReqId(id);
    setActiveTab('detail');
  };

  const handleIngestionComplete = (id) => {
    setSelectedReqId(id);
    setActiveTab('detail');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>
        Loading AREA session...
      </div>
    );
  }

  if (!currentUser || !currentUser.authenticated) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  if (!currentUser.assigned_role) {
    return <LoginView initialNeedsRoleSelection={true} initialSessionUser={currentUser} onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <Navbar
        currentUser={currentUser}
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setSelectedReqId(null);
          setActiveTab(tab);
        }}
        unreadNotificationsCount={unreadNotificationsCount}
        onLogout={handleLogout}
      />

      <main style={{ paddingBottom: '60px' }}>
        {activeTab === 'dashboard' && (
          <DashboardView
            onSelectRequirement={handleSelectRequirement}
            onNavigateIngest={() => setActiveTab('ingest')}
          />
        )}

        {activeTab === 'ingest' && (
          <IngestionView onIngestionComplete={handleIngestionComplete} />
        )}

        {activeTab === 'detail' && selectedReqId && (
          <RequirementDetailView
            requirementId={selectedReqId}
            currentUser={currentUser}
            onBack={() => {
              setSelectedReqId(null);
              setActiveTab('dashboard');
            }}
          />
        )}

        {activeTab === 'notifications' && (
          <NotificationsView currentUser={currentUser} />
        )}

        {activeTab === 'audit' && (
          <AuditView />
        )}
      </main>
    </div>
  );
}

export default App;
