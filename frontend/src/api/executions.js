import apiClient from "./client";

// Get executions belonging to a workflow
export async function getWorkflowExecutions(workflowId, params = {}) {
  const response = await apiClient.get(
    `/workflows/${workflowId}/executions`,
    { params }
  );

  return response.data;
}

// Get individual execution details
export async function getExecutionById(executionId) {
  const response = await apiClient.get(
    `/executions/${executionId}`
  );

  return response.data;
}

// Execute a workflow
export async function executeWorkflow(workflowId, options = {}) {
  const simulateFailure = options.simulate_failure ?? false;

  const payload = {
    simulate_failure: simulateFailure,
    failure_step_order: simulateFailure
      ? Number(options.failure_step_order)
      : null,
    failure_message:
      options.failure_message ||
      "Simulated workflow step failure",
  };

  const response = await apiClient.post(
    `/workflows/${workflowId}/execute`,
    payload
  );

  return response.data;
}
