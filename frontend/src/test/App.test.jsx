import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { LoginView } from '../components/LoginView';
import { Navbar } from '../components/Navbar';
import { DashboardView } from '../components/DashboardView';
import { IngestionView } from '../components/IngestionView';

describe('Frontend Component & Integration Tests', () => {
  
  it('renders LoginView with smart onboarding email input and Google SSO button', () => {
    render(<LoginView onLoginSuccess={() => {}} />);
    expect(screen.getByText('AREA Platform')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('analyst@enterprise.com')).toBeInTheDocument();
    expect(screen.getByText('Sign in with Google Workspace')).toBeInTheDocument();
    expect(screen.queryByText('Microsoft')).not.toBeInTheDocument();
    expect(screen.queryByText('GitHub')).not.toBeInTheDocument();
  });

  it('renders Navbar with user email, role badge, and nav tabs', () => {
    const user = { email: 'ba@xyz.com', assigned_role: 'BUSINESS_ANALYST' };
    render(
      <Navbar
        currentUser={user}
        activeTab="dashboard"
        setActiveTab={() => {}}
        unreadNotificationsCount={2}
        onLogout={() => {}}
      />
    );

    expect(screen.getByText('ba@xyz.com')).toBeInTheDocument();
    expect(screen.getByText('BUSINESS ANALYST')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Ingest Document')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // Unread badge
  });

  it('renders DashboardView metrics cards and ingest action button', async () => {
    render(<DashboardView onSelectRequirement={() => {}} onNavigateIngest={() => {}} />);
    expect(screen.getByText('Requirements Overview')).toBeInTheDocument();
    expect(screen.getByText('+ Ingest New Document')).toBeInTheDocument();
  });

  it('renders IngestionView document dropzone and format specifications', () => {
    render(<IngestionView onIngestionComplete={() => {}} />);
    expect(screen.getByText(/Requirement Document/i)).toBeInTheDocument();
    expect(screen.getByText('Supported formats: PDF, DOCX, XLSX, TXT, EML (UTF-8 encoded)')).toBeInTheDocument();
  });
});
