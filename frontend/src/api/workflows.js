import apiClient from "./client";

export async function getWorkflows(params = {}) {
  const response = await apiClient.get("/workflows", {
    params,
  });

  return response.data;
}

export async function getWorkflowById(workflowId) {
  const response = await apiClient.get(
    `/workflows/${workflowId}`
  );

  return response.data;
}

export async function createWorkflow(workflowData) {
  const response = await apiClient.post(
    "/workflows",
    workflowData
  );

  return response.data;
}
