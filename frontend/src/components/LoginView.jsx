import React, { useState } from 'react';
import { api } from '../services/api';
import { Shield, Lock, Mail, ArrowRight, UserCheck, AlertTriangle, KeyRound, Check, X } from 'lucide-react';

export function LoginView({ onLoginSuccess, initialNeedsRoleSelection = false, initialSessionUser = null }) {
  // Wizard steps: 'EMAIL', 'LOGIN_PASSWORD', 'CREATE_PASSWORD', 'VERIFY_OTP', 'ROLE_SELECTION'
  const [step, setStep] = useState(initialNeedsRoleSelection ? 'ROLE_SELECTION' : 'EMAIL');
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [devOtp, setDevOtp] = useState(null);
  
  const [error, setError] = useState(null);
  const [infoMessage, setInfoMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Role selection state
  const [selectedRole, setSelectedRole] = useState('BUSINESS_ANALYST');
  const [sessionUser, setSessionUser] = useState(initialSessionUser);

  // Live password validation checklist
  const passwordChecks = {
    length: password.length >= 12,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password),
    match: password.length > 0 && password === confirmPassword,
  };
  const isPasswordValid = Object.values(passwordChecks).every(Boolean);

  // --- Step 1: Check Email & Determine Path ---
  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);
    setLoading(true);

    try {
      const res = await api.checkEmail(email);
      if (!res.deliverable) {
        setError(res.detail || 'Email validation failed. Please provide a valid email address.');
        return;
      }

      if (res.exists) {
        // Registered account -> Ask for password
        setStep('LOGIN_PASSWORD');
      } else {
        // New user -> Password creation
        setInfoMessage(res.detail);
        setStep('CREATE_PASSWORD');
      }
    } catch (err) {
      setError(err.message || 'Failed to validate email address.');
    } finally {
      setLoading(false);
    }
  };

  // --- Step 2A: Returning User Login ---
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const loginRes = await api.login(email, password);
      setSessionUser(loginRes);
      if (!loginRes.assigned_role) {
        setStep('ROLE_SELECTION');
      } else {
        onLoginSuccess(loginRes);
      }
    } catch (err) {
      setError(err.message || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  // --- Step 2B: New User Create Password & Trigger OTP ---
  const handleCreatePasswordSubmit = async (e) => {
    e.preventDefault();
    if (!isPasswordValid) {
      setError('Please satisfy all password security rules before proceeding.');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const onboardRes = await api.onboard(email, password);
      setDevOtp(onboardRes.dev_otp);
      setInfoMessage(onboardRes.message);
      setStep('VERIFY_OTP');
    } catch (err) {
      setError(err.message || 'Password registration failed.');
    } finally {
      setLoading(false);
    }
  };

  // --- Step 2C: Verify Email OTP Code ---
  const handleVerifyOtpSubmit = async (e) => {
    e.preventDefault();
    if (!otpCode || otpCode.trim().length < 6) {
      setError('Please enter the 6-digit verification code.');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const verifyRes = await api.verifyEmail(email, otpCode);
      setSessionUser(verifyRes);
      setStep('ROLE_SELECTION');
    } catch (err) {
      setError(err.message || 'Invalid or expired verification code.');
    } finally {
      setLoading(false);
    }
  };

  // --- Step 3: One-Time Role Selection Binding ---
  const handleRoleBinding = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.setRole(selectedRole);
      onLoginSuccess({
        ...sessionUser,
        assigned_role: res.assigned_role,
      });
    } catch (err) {
      setError(err.message || 'Role assignment failed.');
    } finally {
      setLoading(false);
    }
  };

  // --- Render Role Selection View ---
  if (step === 'ROLE_SELECTION') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '20px' }}>
        <div className="glass-panel" style={{ width: '100%', maxWidth: '440px', padding: '36px' }}>
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div style={{ background: 'rgba(99, 102, 241, 0.15)', display: 'inline-flex', padding: '16px', borderRadius: '50%', marginBottom: '12px' }}>
              <UserCheck size={36} color="#6366f1" />
            </div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '700' }}>Initial One-Time Role Selection</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '6px' }}>
              Select your primary project role. Per AREA security policy, this role assignment is permanent and server-bound.
            </p>
          </div>

          {error && (
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '12px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.875rem' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
            {[
              { role: 'BUSINESS_ANALYST', label: 'Business Analyst', desc: 'Ingests documents, reviews AI output, manages clarifications' },
              { role: 'CLIENT', label: 'Client / Stakeholder', desc: 'Answers clarification questions and approves business intent' },
              { role: 'DEVELOPER', label: 'Software Developer', desc: 'Performs technical peer reviews and verifies feasibility' },
              { role: 'QA', label: 'QA Engineer', desc: 'Reviews Gherkin acceptance criteria and testability' },
              { role: 'PRODUCT_OWNER', label: 'Product Owner', desc: 'Final approval authority for requirements freeze' },
            ].map((r) => (
              <div
                key={r.role}
                onClick={() => setSelectedRole(r.role)}
                style={{
                  padding: '14px',
                  borderRadius: '10px',
                  border: selectedRole === r.role ? '2px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.1)',
                  background: selectedRole === r.role ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ fontWeight: '600', color: selectedRole === r.role ? '#818cf8' : 'white' }}>{r.label}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>{r.desc}</div>
              </div>
            ))}
          </div>

          <button className="btn btn-primary" style={{ width: '100%' }} onClick={handleRoleBinding} disabled={loading}>
            {loading ? 'Binding Role...' : 'Confirm Permanent Role Assignment'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '20px' }}>
      <div className="glass-panel" style={{ width: '100%', maxWidth: '440px', padding: '36px' }}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{ background: 'rgba(99, 102, 241, 0.15)', display: 'inline-flex', padding: '14px', borderRadius: '16px', marginBottom: '14px' }}>
            <Shield size={32} color="#6366f1" />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '700', letterSpacing: '-0.02em' }}>AREA Platform</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '4px' }}>
            Automated Requirements Engineering Assistant
          </p>
        </div>

        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '12px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        {infoMessage && (
          <div style={{ background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.3)', color: '#a5b4fc', padding: '12px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.875rem' }}>
            {infoMessage}
          </div>
        )}

        {/* --- STEP 1: EMAIL ENTRY --- */}
        {step === 'EMAIL' && (
          <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px', display: 'block' }}>ENTER YOUR EMAIL ADDRESS</label>
              <div style={{ position: 'relative' }}>
                <Mail size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="email"
                  required
                  className="input-field"
                  style={{ paddingLeft: '40px' }}
                  placeholder="analyst@enterprise.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px', padding: '12px' }} disabled={loading}>
              {loading ? 'Validating Email...' : 'Continue'}
              <ArrowRight size={18} />
            </button>
          </form>
        )}

        {/* --- STEP 2A: RETURNING USER PASSWORD SIGN-IN --- */}
        {step === 'LOGIN_PASSWORD' && (
          <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Welcome back, <strong style={{ color: 'white' }}>{email}</strong>
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px', display: 'block' }}>PASSWORD</label>
              <div style={{ position: 'relative' }}>
                <Lock size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="password"
                  required
                  autoFocus
                  className="input-field"
                  style={{ paddingLeft: '40px' }}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px', padding: '12px' }} disabled={loading}>
              {loading ? 'Signing In...' : 'Sign In'}
              <ArrowRight size={18} />
            </button>

            <button type="button" onClick={() => { setStep('EMAIL'); setPassword(''); setError(null); }} style={{ background: 'none', border: 'none', color: '#818cf8', fontSize: '0.8rem', cursor: 'pointer', marginTop: '4px' }}>
              ← Change email address
            </button>
          </form>
        )}

        {/* --- STEP 2B: NEW USER CREATE STRONG PASSWORD --- */}
        {step === 'CREATE_PASSWORD' && (
          <form onSubmit={handleCreatePasswordSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Creating account for <strong style={{ color: 'white' }}>{email}</strong>
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px', display: 'block' }}>CREATE STRONG PASSWORD</label>
              <div style={{ position: 'relative' }}>
                <Lock size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="password"
                  required
                  className="input-field"
                  style={{ paddingLeft: '40px' }}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px', display: 'block' }}>CONFIRM PASSWORD</label>
              <div style={{ position: 'relative' }}>
                <Lock size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="password"
                  required
                  className="input-field"
                  style={{ paddingLeft: '40px' }}
                  placeholder="••••••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
            </div>

            {/* Password Security Checklist */}
            <div style={{ background: 'rgba(10, 13, 20, 0.6)', padding: '14px', borderRadius: '10px', fontSize: '0.75rem' }}>
              <div style={{ fontWeight: '600', color: 'var(--text-muted)', marginBottom: '8px' }}>PASSWORD SECURITY REQUIREMENTS:</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                {[
                  { key: 'length', text: 'At least 12 chars' },
                  { key: 'uppercase', text: 'One uppercase letter' },
                  { key: 'lowercase', text: 'One lowercase letter' },
                  { key: 'number', text: 'One number (0-9)' },
                  { key: 'special', text: 'One special (!@#$%)' },
                  { key: 'match', text: 'Passwords match' },
                ].map((rule) => {
                  const pass = passwordChecks[rule.key];
                  return (
                    <div key={rule.key} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: pass ? '#4ade80' : '#9ca3af' }}>
                      {pass ? <Check size={14} color="#4ade80" /> : <X size={14} color="#9ca3af" />}
                      <span>{rule.text}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px', padding: '12px' }} disabled={loading || !isPasswordValid}>
              {loading ? 'Creating Password...' : 'Proceed to Verification'}
              <ArrowRight size={18} />
            </button>
          </form>
        )}

        {/* --- STEP 2C: VERIFY EMAIL OTP --- */}
        {step === 'VERIFY_OTP' && (
          <form onSubmit={handleVerifyOtpSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ textAlign: 'center', marginBottom: '8px' }}>
              <div style={{ background: 'rgba(99, 102, 241, 0.15)', display: 'inline-flex', padding: '12px', borderRadius: '50%', marginBottom: '10px' }}>
                <KeyRound size={28} color="#6366f1" />
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '600' }}>Email Ownership Verification</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Enter the 6-digit verification code sent to <strong style={{ color: 'white' }}>{email}</strong>
              </p>
            </div>

            {/* Dev Mode Banner displaying local OTP for manual testing */}
            {devOtp && (
              <div style={{ background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#fbbf24', padding: '12px', borderRadius: '8px', fontSize: '0.8rem', textAlign: 'center' }}>
                <strong>DEV TESTING OTP CODE:</strong> <span style={{ fontSize: '1.1rem', letterSpacing: '3px', fontWeight: '700', color: 'white' }}>{devOtp}</span>
              </div>
            )}

            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px', display: 'block' }}>6-DIGIT VERIFICATION CODE</label>
              <input
                type="text"
                required
                maxLength={10}
                className="input-field"
                style={{ textAlign: 'center', letterSpacing: '6px', fontSize: '1.25rem', fontWeight: '700' }}
                placeholder="123456"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px', padding: '12px' }} disabled={loading}>
              {loading ? 'Verifying Code...' : 'Verify Email & Continue'}
              <ArrowRight size={18} />
            </button>
          </form>
        )}

        {/* --- GOOGLE OAUTH SSO ONLY (Scope Compliant) --- */}
        {step === 'EMAIL' && (
          <div style={{ marginTop: '28px', paddingTop: '20px', borderTop: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', marginBottom: '12px' }}>
              ENTERPRISE SINGLE SIGN-ON (SSO)
            </div>
            <div>
              <button
                key="Google"
                className="btn btn-secondary"
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '0.875rem', padding: '10px' }}
                onClick={() => { window.location.href = '/api/auth/oauth/google/authorize'; }}
              >
                <Shield size={16} color="#4285F4" />
                Sign in with Google Workspace
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', marginTop: '10px', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              <AlertTriangle size={12} color="#f59e0b" />
              <span>Google OAuth credentials configurable in backend .env</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
