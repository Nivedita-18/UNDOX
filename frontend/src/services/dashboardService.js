import { getWorkflows } from "../api/workflows";
import { getWorkflowExecutions } from "../api/executions";
import { getRecoveryPlans } from "../api/recovery";
import { getAuditLogs } from "../api/audit";

export async function getDashboardData() {

  // Fetch all registered workflows
  const workflowsResponse = await getWorkflows({
    limit: 100,
    offset: 0,
  });

  const workflows = Array.isArray(workflowsResponse)
    ? workflowsResponse
    : [];

  // Fetch executions for every workflow
  const executionResults = await Promise.all(
    workflows.map(async (workflow) => {
      try {
        return await getWorkflowExecutions(workflow.id, {
          limit: 100,
          offset: 0,
        });
      } catch (error) {
        console.error(
          `Unable to load executions for workflow ${workflow.id}`,
          error
        );
        return [];
      }
    })
  );

  const executions = executionResults.flat();

  // Fetch recovery plans for each execution
  const recoveryResults = await Promise.all(
    executions.map(async (execution) => {
      try {
        return await getRecoveryPlans(execution.id);
      } catch (error) {
        console.error(
          `Unable to load recovery plans for execution ${execution.id}`,
          error
        );
        return [];
      }
    })
  );

  const recoveryPlans = recoveryResults.flat();

  // Audit access is restricted to ADMIN and OPERATOR.
  // Dashboard should still load for VIEWER users.
  let auditEvents = [];
  let auditAvailable = true;

  try {
    const auditResponse = await getAuditLogs({
      limit: 10,
      offset: 0,
    });

    auditEvents = Array.isArray(auditResponse)
      ? auditResponse
      : [];
  } catch (error) {
    auditAvailable = false;
    console.warn("Audit history is unavailable for this account.");
  }

  // Calculate execution statistics
  const getStatus = (item) =>
    String(item.status || "").toUpperCase();

  const completedExecutions = executions.filter(
    (item) => getStatus(item) === "COMPLETED"
  ).length;

  const failedExecutions = executions.filter(
    (item) => getStatus(item) === "FAILED"
  ).length;

  const runningExecutions = executions.filter(
    (item) =>
      ["RUNNING", "PENDING"].includes(getStatus(item))
  ).length;

  return {
    workflows,
    executions,
    recoveryPlans,
    auditEvents,
    auditAvailable,

    metrics: {
      totalWorkflows: workflows.length,
      totalExecutions: executions.length,
      completedExecutions,
      failedExecutions,
      runningExecutions,
      totalRecoveryPlans: recoveryPlans.length,
    },
  };
}
