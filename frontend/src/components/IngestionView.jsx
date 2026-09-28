import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { FileUp, CheckCircle2, AlertCircle, Cpu, ArrowRight, FileText } from 'lucide-react';

export function IngestionView({ onIngestionComplete }) {
  const [inputMode, setInputMode] = useState('DOCUMENT'); // 'DOCUMENT' | 'TRANSCRIPT'
  const [file, setFile] = useState(null);
  
  // Transcript / Direct Text State
  const [transcriptText, setTranscriptText] = useState('');
  const [transcriptTitle, setTranscriptTitle] = useState('');
  const [sourceType, setSourceType] = useState('TRANSCRIPT');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Pipeline polling state
  const [activeReqId, setActiveReqId] = useState(null);
  const [activeDocId, setActiveDocId] = useState(null);
  const [pipelineState, setPipelineState] = useState(null);
  const [devDiagError, setDevDiagError] = useState(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  const defaultProjectId = 'a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6';

  const wordCount = transcriptText.trim() ? transcriptText.trim().split(/\s+/).length : 0;
  const charCount = transcriptText.length;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const convertFileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const base64String = reader.result.split(',')[1];
        resolve(base64String);
      };
      reader.onerror = (err) => reject(err);
    });
  };

  const handleDocumentSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setDevDiagError(null);

    try {
      const b64 = await convertFileToBase64(file);
      const res = await api.ingestDocument(defaultProjectId, file.name, b64);
      setActiveReqId(res.requirement_id);
      setActiveDocId(res.document_id);
      setPipelineState('INGESTING');
    } catch (err) {
      setError(err.message || 'Document ingestion failed');
      setLoading(false);
    }
  };

  const handleTranscriptSubmit = async (e) => {
    e.preventDefault();
    if (!transcriptText.trim()) {
      setError('Please enter requirement text or a meeting transcript.');
      return;
    }
    if (wordCount < 10) {
      setError('Transcript text is too short. Please provide at least 10 words of requirement text.');
      return;
    }

    setLoading(true);
    setError(null);
    setDevDiagError(null);

    try {
      const res = await api.ingestText(defaultProjectId, transcriptText, transcriptTitle || null, sourceType);
      setActiveReqId(res.requirement_id);
      setActiveDocId(res.document_id);
      setPipelineState('INGESTING');
    } catch (err) {
      setError(err.message || 'Transcript ingestion failed');
      setLoading(false);
    }
  };

  // Poll requirement state until AI_ANALYZED or FAILED
  useEffect(() => {
    if (!activeReqId || pipelineState === 'AI_ANALYZED' || pipelineState === 'FAILED') return;

    const interval = setInterval(async () => {
      try {
        const req = await api.getRequirement(activeReqId);
        setPipelineState(req.current_state);
        if (req.current_state === 'AI_ANALYZED' || req.current_state === 'FAILED') {
          setLoading(false);
          if (req.current_state === 'FAILED') {
            setDevDiagError(req.requirement_data?.error || 'AI Capability Pipeline encountered an unexpected execution error.');
          }
          clearInterval(interval);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeReqId, pipelineState]);

  return (
    <div style={{ maxWidth: '840px', margin: '40px auto', padding: '0 24px' }}>
      <div className="glass-panel" style={{ padding: '36px' }}>
        
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{ background: 'rgba(99, 102, 241, 0.15)', display: 'inline-flex', padding: '16px', borderRadius: '50%', marginBottom: '16px' }}>
            <FileUp size={36} color="#6366f1" />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '700', letterSpacing: '-0.02em' }}>
            Requirement Document & Transcript Ingestion
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '6px' }}>
            Ingest raw BRDs, feature specs, meeting transcripts, or interview notes. The 6-step AI Capability Pipeline will automatically extract requirements, retrieve RAG context, detect gaps & conflicts, and structure user stories.
          </p>
        </div>

        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '14px', borderRadius: '10px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '600' }}>
              <AlertCircle size={18} /> Ingestion Error
            </div>
            <div style={{ fontSize: '0.875rem', marginTop: '4px' }}>{error}</div>
          </div>
        )}

        {!activeReqId ? (
          <div>
            {/* Input Mode Selector Tabs */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', background: 'rgba(10, 13, 20, 0.6)', padding: '6px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
              <button
                type="button"
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  background: inputMode === 'DOCUMENT' ? 'var(--primary, #6366f1)' : 'transparent',
                  color: inputMode === 'DOCUMENT' ? '#ffffff' : 'var(--text-secondary)',
                  fontWeight: '600',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'all 0.2s ease',
                }}
                onClick={() => { setInputMode('DOCUMENT'); setError(null); }}
              >
                <FileText size={18} />
                Upload Document (PDF / DOCX / TXT)
              </button>
              <button
                type="button"
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  background: inputMode === 'TRANSCRIPT' ? 'var(--primary, #6366f1)' : 'transparent',
                  color: inputMode === 'TRANSCRIPT' ? '#ffffff' : 'var(--text-secondary)',
                  fontWeight: '600',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'all 0.2s ease',
                }}
                onClick={() => { setInputMode('TRANSCRIPT'); setError(null); }}
              >
                <Cpu size={18} />
                Paste Transcript / Direct Text
              </button>
            </div>

            {/* TAB A: DOCUMENT UPLOAD */}
            {inputMode === 'DOCUMENT' && (
              <form onSubmit={handleDocumentSubmit}>
                <div
                  style={{
                    border: '2px dashed var(--border-subtle)',
                    borderRadius: '16px',
                    padding: '36px 20px',
                    textAlign: 'center',
                    background: 'rgba(10, 13, 20, 0.5)',
                    cursor: 'pointer',
                    marginBottom: '24px',
                    transition: 'all 0.2s ease',
                  }}
                  onClick={() => document.getElementById('file-input').click()}
                >
                  <input
                    id="file-input"
                    type="file"
                    style={{ display: 'none' }}
                    accept=".pdf,.docx,.xlsx,.txt,.eml,.msg"
                    onChange={handleFileChange}
                  />
                  <FileText size={44} color={file ? '#6366f1' : 'var(--text-muted)'} style={{ margin: '0 auto 12px' }} />
                  {file ? (
                    <div>
                      <div style={{ fontWeight: '600', fontSize: '1rem', color: '#818cf8' }}>{file.name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {(file.size / 1024).toFixed(1)} KB • Click to change file
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ fontWeight: '600', fontSize: '1rem' }}>Click or Drag & Drop document file</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        Supported formats: PDF, DOCX, XLSX, TXT, EML (UTF-8 encoded)
                      </div>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '14px' }}
                  disabled={!file || loading}
                >
                  {loading ? 'Uploading & Initializing...' : 'Upload Document & Execute Capability Pipeline'}
                  <ArrowRight size={18} />
                </button>
              </form>
            )}

            {/* TAB B: TRANSCRIPT / DIRECT TEXT PASTE */}
            {inputMode === 'TRANSCRIPT' && (
              <form onSubmit={handleTranscriptSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                      Source Title / Label (Optional)
                    </label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="e.g. Stakeholder Interview Transcript - Feb 2026"
                      value={transcriptTitle}
                      onChange={(e) => setTranscriptTitle(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'rgba(10, 13, 20, 0.5)' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                      Source Type
                    </label>
                    <select
                      className="input-field"
                      value={sourceType}
                      onChange={(e) => setSourceType(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'rgba(10, 13, 20, 0.5)' }}
                    >
                      <option value="TRANSCRIPT">Meeting Transcript</option>
                      <option value="DIRECT_TEXT">Plain Requirements Text</option>
                      <option value="MEETING_MINUTES">Meeting Minutes</option>
                      <option value="EMAIL">Email Content</option>
                    </select>
                  </div>
                </div>

                <div style={{ marginBottom: '16px', position: 'relative' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Requirement Content / Transcript Text <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <textarea
                    rows={8}
                    className="input-field"
                    placeholder="Paste your meeting transcript, Teams/Zoom notes, stakeholder interview text, or raw software requirements here..."
                    value={transcriptText}
                    onChange={(e) => setTranscriptText(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '14px',
                      borderRadius: '12px',
                      background: 'rgba(10, 13, 20, 0.6)',
                      color: 'var(--text-primary)',
                      fontSize: '0.875rem',
                      lineHeight: '1.6',
                      fontFamily: 'inherit',
                      resize: 'vertical',
                    }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: wordCount < 10 && transcriptText ? '#f87171' : 'var(--text-muted)', marginTop: '6px' }}>
                    <span>{wordCount < 10 && transcriptText ? 'Minimum 10 words required' : 'Supports markdown and plain text'}</span>
                    <span>{wordCount} words • {charCount} characters</span>
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '14px' }}
                  disabled={!transcriptText.trim() || wordCount < 10 || loading}
                >
                  {loading ? 'Processing Transcript...' : 'Analyze Transcript & Execute AI Capability Pipeline'}
                  <ArrowRight size={18} />
                </button>
              </form>
            )}
          </div>
        ) : (
          <div style={{ padding: '24px', background: 'rgba(10, 13, 20, 0.6)', borderRadius: '14px', border: '1px solid var(--border-subtle)' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Cpu size={20} color="#6366f1" />
              AI Capability Pipeline Execution
            </h3>

            {/* Pipeline Stage Tracker */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
              {[
                { stage: 'INGESTING', label: '1. Text Extraction & Normalization' },
                { stage: 'AI_ANALYZING', label: '2. 6-Step AI Capability Execution (Extraction -> Quality)' },
                { stage: 'AI_ANALYZED', label: '3. Analysis Complete & Assigned to Business Analyst' },
              ].map((step, idx) => {
                const isComplete = pipelineState === 'AI_ANALYZED' || (idx === 0 && (pipelineState === 'INGESTING' || pipelineState === 'AI_ANALYZED'));
                const isCurrent = (pipelineState === 'INGESTING' && idx === 0) || (pipelineState === 'AI_ANALYZING' && idx === 1);
                const isFailed = pipelineState === 'FAILED';

                return (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', borderRadius: '8px', background: isCurrent ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)', border: isCurrent ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent' }}>
                    {isComplete && pipelineState !== 'FAILED' ? (
                      <CheckCircle2 size={20} color="#10b981" />
                    ) : isFailed ? (
                      <AlertCircle size={20} color="#ef4444" />
                    ) : (
                      <div style={{ width: '20px', height: '20px', borderRadius: '50%', border: '2px solid #6366f1', borderTopColor: 'transparent', animation: 'spin 1s linear infinite' }} />
                    )}
                    <span style={{ fontSize: '0.875rem', fontWeight: isCurrent ? '600' : '400', color: isFailed ? '#f87171' : 'var(--text-primary)' }}>
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>

            {pipelineState === 'AI_ANALYZED' && (
              <button
                className="btn btn-primary"
                style={{ width: '100%' }}
                onClick={() => onIngestionComplete(activeReqId)}
              >
                View AI-Generated Requirement Artifacts <ArrowRight size={18} />
              </button>
            )}

            {pipelineState === 'FAILED' && (
              <div>
                <div style={{ color: '#f87171', fontSize: '0.875rem', marginBottom: '16px' }}>
                  Pipeline failed during AI analysis. Error logged to audit trail and notification sent to Business Analyst.
                </div>

                {/* Development Diagnostic Accordion */}
                <div style={{ marginBottom: '16px', background: 'rgba(0,0,0,0.4)', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.3)', overflow: 'hidden' }}>
                  <button
                    type="button"
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      background: 'rgba(239,68,68,0.1)',
                      border: 'none',
                      color: '#f87171',
                      fontSize: '0.75rem',
                      fontWeight: '600',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                    onClick={() => setShowDiagnostics(!showDiagnostics)}
                  >
                    <span>🛠️ Developer Diagnostic Details</span>
                    <span>{showDiagnostics ? '▲ Hide' : '▼ Expand'}</span>
                  </button>

                  {showDiagnostics && (
                    <div style={{ padding: '14px', fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                      <div style={{ marginBottom: '6px' }}><strong style={{ color: '#ffffff' }}>Requirement ID:</strong> {activeReqId}</div>
                      <div style={{ marginBottom: '6px' }}><strong style={{ color: '#ffffff' }}>Document ID:</strong> {activeDocId || 'N/A'}</div>
                      <div style={{ marginBottom: '6px' }}><strong style={{ color: '#ffffff' }}>Failed Stage:</strong> AI Capability Pipeline Execution</div>
                      <div><strong style={{ color: '#ffffff' }}>Reason:</strong> {devDiagError || 'Check Uvicorn backend log for detailed traceback.'}</div>
                    </div>
                  )}
                </div>

                <button
                  className="btn btn-secondary"
                  style={{ width: '100%' }}
                  onClick={() => { setActiveReqId(null); setActiveDocId(null); setPipelineState(null); setFile(null); setTranscriptText(''); setDevDiagError(null); }}
                >
                  Try Another Input
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
