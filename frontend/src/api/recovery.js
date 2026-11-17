import apiClient from "./client";

// Get recovery plans for a particular execution
export async function getRecoveryPlans(executionId) {
  const response = await apiClient.get(
    `/executions/${executionId}/recovery-plans`
  );

  return response.data;
}

// Get a specific recovery plan
export async function getRecoveryPlanById(planId) {
  const response = await apiClient.get(
    `/recovery-plans/${planId}`
  );

  return response.data;
}

// Generate a recovery plan
export async function generateRecoveryPlan(executionId) {
  const response = await apiClient.post(
    `/executions/${executionId}/recovery-plans`
  );

  return response.data;
}

// Check recovery plan conflicts
export async function checkRecoveryConflicts(planId) {
  const response = await apiClient.get(
    `/recovery-plans/${planId}/conflicts`
  );

  return response.data;
}

// Approve a recovery plan
export async function approveRecoveryPlan(planId, decision) {
  const response = await apiClient.post(
    `/recovery-plans/${planId}/approve`,
    decision
  );

  return response.data;
}

// Reject a recovery plan
export async function rejectRecoveryPlan(planId, decision) {
  const response = await apiClient.post(
    `/recovery-plans/${planId}/reject`,
    decision
  );

  return response.data;
}

// Execute an approved recovery plan
export async function executeRecoveryPlan(planId) {
  const response = await apiClient.post(
    `/recovery-plans/${planId}/execute`
  );

  return response.data;
}

// Check recovery execution progress
export async function getRecoveryExecutionStatus(planId) {
  const response = await apiClient.get(
    `/recovery-plans/${planId}/execution-status`
  );

  return response.data;
}
