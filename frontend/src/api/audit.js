import apiClient from "./client";

// Get and filter audit events
export async function getAuditLogs(params = {}) {
  const response = await apiClient.get(
    "/api/v1/audit-events",
    { params }
  );

  return response.data;
}

// Get one audit event
export async function getAuditEventById(eventId) {
  const response = await apiClient.get(
    `/api/v1/audit-events/${eventId}`
  );

  return response.data;
}

// Get audit events for an execution
export async function getExecutionAuditLogs(executionId) {
  const response = await apiClient.get(
    `/api/v1/executions/${executionId}/audit-events`
  );

  return response.data;
}

// Get audit events for a recovery plan
export async function getRecoveryAuditLogs(planId) {
  const response = await apiClient.get(
    `/api/v1/recovery-plans/${planId}/audit-events`
  );

  return response.data;
}
