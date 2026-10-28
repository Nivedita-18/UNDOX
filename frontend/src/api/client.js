/**
 * UNDOX Frontend API Client
 * Seamlessly interfaces with the FastAPI backend endpoints with token injection,
 * error normalization, and support for all system operations.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const token = localStorage.getItem('undox_token');
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  let response;
  try {
    response = await fetch(url, config);
  } catch (err) {
    throw new ApiError(`Network error connecting to backend: ${err.message}`, 0, null);
  }

  let data = null;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    if (data && typeof data === 'object' && data.detail) {
      if (typeof data.detail === 'string') {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
      }
    }

    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('undox:unauthorized'));
    }

    throw new ApiError(errorMessage, response.status, data);
  }

  return data;
}

export const api = {
  // System Health
  health: {
    check: () => request('/health'),
    dbCheck: () => request('/health/db'),
  },

  // Authentication & Profile
  auth: {
    register: (username, email, password, role = 'VIEWER') =>
      request('/auth/register', {
        method: 'POST',
        body: { username, email, password, role },
      }),
    login: (username, password) =>
      request('/auth/login', {
        method: 'POST',
        body: { username, password },
      }),
    getMe: () => request('/auth/me'),
  },

  // Workflows
  workflows: {
    list: (limit = 50, offset = 0) =>
      request(`/workflows?limit=${limit}&offset=${offset}`),
    get: (id) => request(`/workflows/${id}`),
    create: (workflowData) =>
      request('/workflows', {
        method: 'POST',
        body: workflowData,
      }),
  },

  // Executions
  executions: {
    create: (workflowId, failureSimulation = null) => {
      const payload = { workflow_id: workflowId };
      if (failureSimulation) {
        payload.failure_simulation = failureSimulation;
      }
      return request('/executions', {
        method: 'POST',
        body: payload,
      });
    },
    get: (id) => request(`/executions/${id}`),
  },

  // Recovery Planning & Execution
  recovery: {
    createPlan: (executionId, payload = {}) =>
      request(`/executions/${executionId}/recovery-plans`, {
        method: 'POST',
        body: payload,
      }),
    getPlan: (planId) => request(`/recovery-plans/${planId}`),
    listPlansForExecution: (executionId) =>
      request(`/executions/${executionId}/recovery-plans`),
    getConflicts: (planId) => request(`/recovery-plans/${planId}/conflicts`),
    approvePlan: (planId, payload = {}) =>
      request(`/recovery-plans/${planId}/approve`, {
        method: 'POST',
        body: payload,
      }),
    rejectPlan: (planId, reason) =>
      request(`/recovery-plans/${planId}/reject`, {
        method: 'POST',
        body: { reason },
      }),
    executePlan: (planId, payload = {}) =>
      request(`/recovery-plans/${planId}/execute`, {
        method: 'POST',
        body: payload,
      }),
    getExecutionStatus: (planId) =>
      request(`/recovery-plans/${planId}/execution-status`),
  },

  // Audit Logs
  audit: {
    listEvents: (params = {}) => {
      const query = new URLSearchParams();
      if (params.execution_id) query.append('execution_id', params.execution_id);
      if (params.recovery_plan_id) query.append('recovery_plan_id', params.recovery_plan_id);
      if (params.event_type) query.append('event_type', params.event_type);
      if (params.outcome) query.append('outcome', params.outcome);
      if (params.limit) query.append('limit', params.limit);
      if (params.offset !== undefined) query.append('offset', params.offset);

      const qs = query.toString();
      return request(`/api/v1/audit-events${qs ? `?${qs}` : ''}`);
    },
    getEvent: (id) => request(`/api/v1/audit-events/${id}`),
    getEventsForExecution: (executionId) =>
      request(`/api/v1/executions/${executionId}/audit-events`),
    getEventsForPlan: (planId) =>
      request(`/api/v1/recovery-plans/${planId}/audit-events`),
  },
};

export default api;
