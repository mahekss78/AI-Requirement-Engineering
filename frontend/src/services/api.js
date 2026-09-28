/**
 * frontend/src/services/api.js
 * =============================
 * Central REST API client for the AREA backend.
 * Consumes existing FastAPI backend endpoints using native fetch.
 * Uses credentials: 'include' for server-managed HttpOnly session cookies,
 * plus optional Bearer token header fallback.
 */

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

class APIClient {
  constructor() {
    this.sessionToken = localStorage.getItem('area_session_token') || null;
  }

  setSessionToken(token) {
    this.sessionToken = token;
    if (token) {
      localStorage.setItem('area_session_token', token);
    } else {
      localStorage.removeItem('area_session_token');
    }
  }

  async _request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }

    const config = {
      credentials: 'include', // Support HttpOnly area_session cookie
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.detail || data.message || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(errorMsg);
      }
      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err.message);
      throw err;
    }
  }

  // --- Auth APIs ---
  async checkEmail(email) {
    return this._request('/api/auth/check-email', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async onboard(email, password) {
    return this._request('/api/auth/onboard', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async verifyEmail(email, code) {
    return this._request('/api/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    });
  }

  async login(email, password) {
    const res = await this._request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (res.session_token) {
      this.setSessionToken(res.session_token);
    }
    return res;
  }

  async register(email, password) {
    return this._request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async getSession() {
    return this._request('/api/auth/session', { method: 'GET' });
  }

  async setRole(role) {
    return this._request('/api/auth/role', {
      method: 'POST',
      body: JSON.stringify({ role }),
    });
  }

  async logout() {
    try {
      await this._request('/api/auth/logout', { method: 'POST' });
    } finally {
      this.setSessionToken(null);
    }
  }

  // --- Requirements & Ingestion ---
  async ingestDocument(projectId, fileName, fileContentBase64) {
    return this._request('/api/requirements/ingest', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        file_name: fileName,
        file_content_base64: fileContentBase64,
      }),
    });
  }

  async ingestText(projectId, text, title = null, sourceType = 'TRANSCRIPT') {
    return this._request('/api/requirements/ingest-text', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        text,
        title,
        source_type: sourceType,
      }),
    });
  }

  async getRequirements(projectId = null) {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this._request(`/api/requirements${query}`, { method: 'GET' });
  }

  async getRequirement(id) {
    return this._request(`/api/requirements/${id}`, { method: 'GET' });
  }

  async transitionState(id, event, rationale = null, targetRole = null) {
    return this._request(`/api/requirements/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify({
        event,
        rationale,
        target_role: targetRole,
      }),
    });
  }

  // --- Clarifications & Comments ---
  async getClarifications(reqId) {
    return this._request(`/api/requirements/${reqId}/clarifications`, { method: 'GET' });
  }

  async addClarification(reqId, question, assignedRole = 'CLIENT') {
    return this._request(`/api/requirements/${reqId}/clarifications`, {
      method: 'POST',
      body: JSON.stringify({
        question_text: question,
        target_role: assignedRole,
      }),
    });
  }

  async answerClarification(reqId, qId, answerText) {
    return this._request(`/api/requirements/${reqId}/clarifications/${qId}`, {
      method: 'PUT',
      body: JSON.stringify({ answer_text: answerText }),
    });
  }

  async getComments(reqId) {
    return this._request(`/api/requirements/${reqId}/comments`, { method: 'GET' });
  }

  async addComment(reqId, commentText, parentId = null) {
    return this._request(`/api/requirements/${reqId}/comments`, {
      method: 'POST',
      body: JSON.stringify({
        comment_text: commentText,
        parent_comment_id: parentId,
      }),
    });
  }

  // --- Dashboard & Metrics ---
  async getDashboardMetrics() {
    return this._request('/api/dashboard/metrics', { method: 'GET' });
  }

  async getNotifications() {
    return this._request('/api/notifications', { method: 'GET' });
  }

  async markNotificationRead(id) {
    return this._request(`/api/notifications/${id}/read`, { method: 'PUT' });
  }

  async getAuditLogs(reqId = null) {
    const query = reqId ? `?requirement_id=${reqId}` : '';
    return this._request(`/api/audit-logs${query}`, { method: 'GET' });
  }

  async getVersions(reqId) {
    return this._request(`/api/requirements/${reqId}/versions`, { method: 'GET' });
  }

  async rollbackVersion(reqId, targetVersion) {
    return this._request(`/api/requirements/${reqId}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ target_version: targetVersion }),
    });
  }
}

export const api = new APIClient();
