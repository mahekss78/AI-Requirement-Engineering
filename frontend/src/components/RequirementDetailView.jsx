import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import {
  FileText, Shield, CheckCircle2, AlertTriangle, Cpu, History, MessageSquare,
  ArrowLeft, RotateCcw, AlertCircle, Sparkles, ExternalLink
} from 'lucide-react';

export function RequirementDetailView({ requirementId, currentUser, onBack }) {
  const [req, setReq] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Clarification / Comment / Version / Audit state
  const [clarifications, setClarifications] = useState([]);
  const [comments, setComments] = useState([]);
  const [versions, setVersions] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  // Transition / Input state
  const [transitionRationale, setTransitionRationale] = useState('');
  const [transitionTargetRole, setTransitionTargetRole] = useState('DEVELOPER');
  const [newQuestionText, setNewQuestionText] = useState('');
  const [answerTexts, setAnswerTexts] = useState({});
  const [newCommentText, setNewCommentText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRequirement(requirementId);
      setReq(data);

      // Fetch related data in parallel
      const [cRes, cmRes, vRes, aRes] = await Promise.all([
        api.getClarifications(requirementId).catch(() => []),
        api.getComments(requirementId).catch(() => []),
        api.getVersions(requirementId).catch(() => []),
        api.getAuditLogs(requirementId).catch(() => []),
      ]);

      setClarifications(cRes);
      setComments(cmRes);
      setVersions(vRes);
      setAuditLogs(aRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch requirement details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [requirementId]);

  // Handle Lifecycle State Transitions
  const handleTransition = async (event) => {
    setSubmitting(true);
    setError(null);
    try {
      await api.transitionState(requirementId, event, transitionRationale, transitionTargetRole);
      setTransitionRationale('');
      await fetchDetail();
    } catch (err) {
      setError(err.message || `Transition '${event}' failed`);
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Clarification Question Submission
  const handleAddQuestion = async (e) => {
    e.preventDefault();
    if (!newQuestionText.trim()) return;
    setSubmitting(true);
    try {
      await api.addClarification(requirementId, newQuestionText, 'CLIENT');
      setNewQuestionText('');
      const cRes = await api.getClarifications(requirementId);
      setClarifications(cRes);
    } catch (err) {
      setError(err.message || 'Failed to submit question');
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Clarification Answer Submission
  const handleAnswerQuestion = async (qId) => {
    const text = answerTexts[qId];
    if (!text?.trim()) return;
    setSubmitting(true);
    try {
      await api.answerClarification(requirementId, qId, text);
      setAnswerTexts({ ...answerTexts, [qId]: '' });
      const cRes = await api.getClarifications(requirementId);
      setClarifications(cRes);
    } catch (err) {
      setError(err.message || 'Failed to submit answer');
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Comment Submission
  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!newCommentText.trim()) return;
    setSubmitting(true);
    try {
      await api.addComment(requirementId, newCommentText);
      setNewCommentText('');
      const cmRes = await api.getComments(requirementId);
      setComments(cmRes);
    } catch (err) {
      setError(err.message || 'Failed to add comment');
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Rollback
  const handleRollback = async (targetVer) => {
    if (!window.confirm(`Are you sure you want to rollback to version ${targetVer}?`)) return;
    setSubmitting(true);
    try {
      await api.rollbackVersion(requirementId, targetVer);
      await fetchDetail();
    } catch (err) {
      setError(err.message || 'Rollback failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div style={{ maxWidth: '1200px', margin: '60px auto', textAlign: 'center', color: 'var(--text-muted)' }}>Loading requirement detail...</div>;
  }

  if (!req) {
    return <div style={{ maxWidth: '1200px', margin: '60px auto', textAlign: 'center', color: '#f87171' }}>Requirement not found.</div>;
  }

  const reqData = req.requirement_data || {};
  const structuring = reqData.structuring || {};
  const metadata = structuring.metadata || reqData.metadata || {};
  const userStories = structuring.user_stories || reqData.user_stories || [];
  const acceptanceCriteria = structuring.acceptance_criteria || reqData.acceptance_criteria || [];
  const incompleteStories = structuring.incomplete_stories || [];
  const extraction = reqData.extraction || {};
  const context = reqData.context || {};
  const gapReport = reqData.gap_detection || {};
  const conflictReport = reqData.conflict_detection || {};
  const qualityReport = reqData.quality || {};
  const pipelineStatus = reqData.pipeline_status || null;
  const capabilityStatuses = reqData.capability_statuses || {};

  const getQualityScore = (val) => {
    if (val === null || val === undefined) return null;
    if (typeof val === 'object' && val !== null) return val.score;
    if (typeof val === 'number') return val;
    return null;
  };
  const getQualityReason = (val) => {
    if (typeof val === 'object' && val !== null) return val.reason || null;
    return null;
  };
  const evaluationStatus = qualityReport.evaluation_status || (qualityReport.ai_status === 'fallback_deterministic' ? 'ai_unavailable' : null);

  const allRequirements = [
    ...(extraction.functional_requirements || []).map(r => `[FR] ${r.statement || r}`),
    ...(extraction.non_functional_requirements || []).map(r => `[NFR] ${r.statement || r}`),
    ...(extraction.business_rules || []).map(r => `[BR] ${r.statement || r}`),
  ];

  const userRole = currentUser?.assigned_role || 'GUEST';

  return (
    <div style={{ maxWidth: '1300px', margin: '28px auto', padding: '0 24px' }}>
      
      {/* Top Header & Back Button */}
      <button className="btn btn-secondary" style={{ marginBottom: '20px' }} onClick={onBack}>
        <ArrowLeft size={16} /> Back to Dashboard
      </button>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '14px', borderRadius: '10px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Main Title & Lifecycle Card */}
      <div className="glass-panel" style={{ padding: '28px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <span className={`badge badge-${req.current_state.toLowerCase().replace('_', '-')}`}>
                {req.current_state}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                v{req.version}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Assigned: <strong>{req.assigned_role}</strong>
              </span>
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: '700', letterSpacing: '-0.02em' }}>{req.title}</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '6px' }}>
              {metadata.summary || 'AI-analyzed requirement specification'}
            </p>
          </div>

          {/* Scores Overview Pill */}
          <div style={{ display: 'flex', gap: '16px', background: 'rgba(10, 13, 20, 0.6)', padding: '12px 20px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '600' }}>CONFIDENCE</div>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: req.confidence_score >= 80 ? '#10b981' : '#f59e0b' }}>
                {req.confidence_score?.toFixed(1)}%
              </div>
            </div>
            <div style={{ width: '1px', background: 'var(--border-subtle)' }} />
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '600' }}>HEALTH</div>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: req.health_score >= 80 ? '#10b981' : '#ef4444' }}>
                {req.health_score?.toFixed(1)}%
              </div>
            </div>
          </div>
        </div>

        {/* Human-in-the-loop Action Controls */}
        <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
            <Sparkles size={16} color="#6366f1" />
            <span style={{ color: 'var(--text-secondary)' }}>Human Authorization Controls:</span>
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {req.current_state === 'AI_ANALYZED' && (
              <button className="btn btn-primary" onClick={() => handleTransition('APPROVE_DRAFT')} disabled={submitting}>
                Submit for Peer Review
              </button>
            )}
            {req.current_state === 'PEER_REVIEW' && (
              <button className="btn btn-primary" onClick={() => handleTransition('APPROVE_PEER_REVIEW')} disabled={submitting}>
                Approve Peer Review
              </button>
            )}
            {req.current_state === 'APPROVED' && (
              <>
                <button className="btn btn-secondary" onClick={() => handleTransition('MARK_JIRA_SYNCED')} disabled={submitting}>
                  Mark Jira Synced
                </button>
                <button className="btn btn-primary" onClick={() => handleTransition('FREEZE')} disabled={submitting}>
                  Freeze Requirement (Major v1.0.0)
                </button>
              </>
            )}
            {req.current_state === 'JIRA_SYNCED' && (
              <button className="btn btn-primary" onClick={() => handleTransition('FREEZE')} disabled={submitting}>
                Freeze Requirement (Major v1.0.0)
              </button>
            )}
          </div>
        </div>

        {/* Jira Integration Banner Stub per Section 9 */}
        <div style={{ marginTop: '16px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(14, 165, 233, 0.08)', border: '1px solid rgba(14, 165, 233, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', color: '#38bdf8' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ExternalLink size={14} />
            <span>Jira Export Status: <strong>Stub 501</strong> (Reserved for Jira Integration Phase)</span>
          </div>
          <span style={{ color: 'var(--text-muted)' }}>No fake sync manufactured</span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
        {[
          { id: 'overview', label: 'Overview & Metadata', icon: FileText },
          { id: 'analysis', label: 'AI Analysis & Gaps', icon: Cpu },
          { id: 'structured', label: 'Structured Stories (Gherkin)', icon: Sparkles },
          { id: 'quality', label: 'Quality Dimensions', icon: Shield },
          { id: 'clarifications', label: `Clarifications (${clarifications.length})`, icon: MessageSquare },
          { id: 'versions', label: `Versions (${versions.length})`, icon: History },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 16px',
                borderRadius: '8px',
                border: 'none',
                background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                color: isActive ? '#818cf8' : 'var(--text-secondary)',
                fontWeight: isActive ? '600' : '400',
                fontSize: '0.875rem',
                cursor: 'pointer',
              }}
            >
              <Icon size={16} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px' }}>Requirement Overview</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.875rem' }}>
              <div><strong>Primary Actor:</strong> {metadata.primary_actor || 'Not specified'}</div>
              <div><strong>Domain Context:</strong> {metadata.domain || 'Not determined'}</div>
              <div><strong>Created At:</strong> {new Date(req.created_at).toLocaleString()}</div>
              <div><strong>Last Updated:</strong> {new Date(req.updated_at).toLocaleString()}</div>
            </div>

            <h4 style={{ fontSize: '1rem', fontWeight: '600', marginTop: '24px', marginBottom: '12px' }}>Summary Statement</h4>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
              {metadata.summary || 'No summary provided.'}
            </p>
          </div>

          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px' }}>Comments & Discussion</h3>
            
            <div style={{ maxHeight: '300px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px' }}>
              {comments.length === 0 ? (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No inline comments yet.</div>
              ) : (
                comments.map((cm) => (
                  <div key={cm.id} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#818cf8' }}>{cm.author_role}</div>
                    <div style={{ fontSize: '0.85rem', marginTop: '2px' }}>{cm.comment_text}</div>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={handleAddComment}>
              <input
                type="text"
                className="input-field"
                placeholder="Add inline comment..."
                value={newCommentText}
                onChange={(e) => setNewCommentText(e.target.value)}
                style={{ marginBottom: '8px' }}
              />
              <button type="submit" className="btn btn-secondary" style={{ width: '100%', fontSize: '0.75rem' }} disabled={submitting}>
                Post Comment
              </button>
            </form>
          </div>
        </div>
      )}

      {/* TAB 2: AI ANALYSIS */}
      {activeTab === 'analysis' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Extracted Statements */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px', color: '#818cf8' }}>
              1. Extracted Requirement Statements
            </h3>
            <ul style={{ paddingLeft: '20px', color: 'var(--text-primary)', fontSize: '0.9rem', lineHeight: 1.7 }}>
              {(allRequirements.length > 0 ? allRequirements : ['No statements extracted']).map((stmt, idx) => (
                <li key={idx}>{stmt}</li>
              ))}
            </ul>
          </div>

          {/* Context & RAG Fragments */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px', color: '#38bdf8' }}>
              2. RAG Context & Knowledge Fragments
            </h3>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              <strong>Mapped Sub-Systems:</strong> {(context.related_entities || []).join(', ') || 'None'}
            </div>
            <div style={{ background: 'rgba(10, 13, 20, 0.7)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
              {context.enrichment_notes || 'RAG retrieval complete.'}
            </div>
          </div>

          {/* Gaps & Conflicts Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            
            {/* Gaps */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} /> Identified Gaps ({(gapReport.gaps || []).length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {(gapReport.gaps || []).length === 0 ? (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No gaps detected.</div>
                ) : (
                  (gapReport.gaps || []).map((gap, idx) => (
                    <div key={idx} style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.2)', fontSize: '0.85rem' }}>
                      <strong>{gap.gap_id || `G-${idx+1}`}:</strong> {gap.description || JSON.stringify(gap)}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Conflicts */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={18} /> Identified Conflicts ({(conflictReport.conflicts || []).length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {(conflictReport.conflicts || []).length === 0 ? (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No conflicts detected.</div>
                ) : (
                  (conflictReport.conflicts || []).map((c, idx) => (
                    <div key={idx} style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)', fontSize: '0.85rem' }}>
                      <span className="badge badge-failed" style={{ marginBottom: '4px' }}>{c.severity || 'HIGH'}</span>
                      <div style={{ marginTop: '4px' }}>{c.description || JSON.stringify(c)}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: STRUCTURED REQUIREMENT */}
      {activeTab === 'structured' && (
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: '600', marginBottom: '20px' }}>User Stories & Gherkin Acceptance Criteria</h3>

          {userStories.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No user stories structured yet.</div>
          ) : (
            userStories.map((us, idx) => (
              <div key={idx} style={{ background: 'rgba(10, 13, 20, 0.6)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-subtle)', marginBottom: '20px' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: '700', color: '#818cf8', marginBottom: '4px' }}>{us.id || `US-${idx+1}`}</div>
                {us.status === 'needs_clarification' ? (
                  <div style={{ padding: '10px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '6px', color: '#f59e0b', fontSize: '0.9rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <AlertTriangle size={16} /> Needs Clarification
                  </div>
                ) : (
                  <div style={{ fontSize: '1.05rem', fontWeight: '600', marginBottom: '16px' }}>
                    As a <em>{us.as_a || '(unspecified)'}</em>, I want to <em>{us.i_want || '(unspecified)'}</em> so that <em>{us.so_that || '(unspecified)'}</em>.
                  </div>
                )}

                <h5 style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '10px' }}>Gherkin Acceptance Criteria:</h5>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {acceptanceCriteria.filter(ac => ac.story_id === us.id).map((ac, acIdx) => (
                    <div key={acIdx} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px', borderRadius: '8px', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      <div><strong style={{ color: '#38bdf8' }}>GIVEN</strong> {ac.given}</div>
                      <div><strong style={{ color: '#fbbf24' }}>WHEN</strong> {ac.when}</div>
                      <div><strong style={{ color: '#34d399' }}>THEN</strong> {ac.then}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* TAB 4: QUALITY EVALUATION */}
      {activeTab === 'quality' && (
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: '600', marginBottom: '20px' }}>5 PDS Quality Dimension Scores</h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '28px' }}>
            {[
              { dim: 'Completeness', val: qualityReport.completeness },
              { dim: 'Clarity', val: qualityReport.clarity },
              { dim: 'Consistency', val: qualityReport.consistency },
              { dim: 'Testability', val: qualityReport.testability },
              { dim: 'Traceability', val: qualityReport.traceability },
            ].map((q) => {
              const score = getQualityScore(q.val);
              const reason = getQualityReason(q.val);
              return (
                <div key={q.dim} style={{ background: 'rgba(10, 13, 20, 0.6)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>{q.dim}</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '700', color: score !== null ? '#818cf8' : 'var(--text-muted)', margin: '6px 0' }}>
                    {score !== null ? `${score.toFixed(1)}%` : '—'}
                  </div>
                  {reason && <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{reason}</div>}
                </div>
              );
            })}
          </div>

          {evaluationStatus === 'ai_unavailable' && (
            <div style={{ marginBottom: '20px', padding: '12px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '8px', color: '#f59e0b', fontSize: '0.85rem' }}>
              Quality evaluation performed via deterministic fallback. AI scores unavailable.
            </div>
          )}

          <div style={{ background: 'rgba(10, 13, 20, 0.6)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
            <h4 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '8px' }}>Quality Summary</h4>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{qualityReport.quality_summary || 'Quality evaluation complete.'}</p>
          </div>
        </div>
      )}

      {/* TAB 5: CLARIFICATIONS */}
      {activeTab === 'clarifications' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px' }}>Stakeholder Q&A Clarifications</h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {clarifications.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No open clarifications.</div>
              ) : (
                clarifications.map((c) => (
                  <div key={c.id} style={{ background: 'rgba(10, 13, 20, 0.6)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      <span>Question for: <strong>{c.assigned_role}</strong></span>
                      <span className={`badge ${c.status === 'ANSWERED' ? 'badge-approved' : 'badge-clarifying'}`}>{c.status}</span>
                    </div>
                    <div style={{ fontWeight: '600', fontSize: '0.9rem', marginBottom: '12px' }}>{c.question_text}</div>

                    {c.answer_text ? (
                      <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '10px', borderRadius: '6px', fontSize: '0.85rem', color: '#34d399' }}>
                        <strong>Answer:</strong> {c.answer_text}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <input
                          type="text"
                          className="input-field"
                          placeholder="Provide clarification answer..."
                          value={answerTexts[c.id] || ''}
                          onChange={(e) => setAnswerTexts({ ...answerTexts, [c.id]: e.target.value })}
                        />
                        <button className="btn btn-primary" onClick={() => handleAnswerQuestion(c.id)} disabled={submitting}>
                          Submit Answer
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px' }}>Add Clarification Question</h3>
            <form onSubmit={handleAddQuestion}>
              <textarea
                className="input-field"
                rows={4}
                placeholder="Formulate targeted question for Client/Stakeholder..."
                value={newQuestionText}
                onChange={(e) => setNewQuestionText(e.target.value)}
                style={{ marginBottom: '12px' }}
              />
              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
                Dispatch Question to Client
              </button>
            </form>
          </div>
        </div>
      )}

      {/* TAB 6: VERSIONS & ROLLBACK */}
      {activeTab === 'versions' && (
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: '600', marginBottom: '20px' }}>Semantic Version History & Rollbacks</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {versions.map((ver) => (
              <div key={ver.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', background: 'rgba(10, 13, 20, 0.6)', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', fontSize: '1rem', color: '#818cf8' }}>v{ver.version}</span>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{ver.change_rationale || 'Snapshot saved'}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>{new Date(ver.created_at).toLocaleString()}</div>
                </div>

                {ver.version !== req.version && (
                  <button className="btn btn-danger" style={{ fontSize: '0.75rem' }} onClick={() => handleRollback(ver.version)} disabled={submitting}>
                    <RotateCcw size={14} /> Rollback to v{ver.version}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
