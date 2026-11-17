# UNDOX - Workflow Failure Recovery System

## 1. Project Architecture

### Frontend
- React
- Vite
- React Router
- Axios
- Lucide React

### Backend
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT authentication
- Argon2 password hashing

## 2. Main Modules

1. Authentication
2. Workflow Management
3. Workflow Step Builder
4. Execution Management
5. Failure Simulation
6. Recovery Plan Generation
7. Conflict Inspection
8. Recovery Approval and Rejection
9. Recovery Execution
10. Audit History
11. User Profile and Role Management

## 3. Backend API Routes

### Authentication
- POST /auth/register
- POST /auth/login
- GET /auth/me

### Workflows
- POST /workflows
- GET /workflows
- GET /workflows/{workflow_id}

### Executions
- POST /workflows/{workflow_id}/execute
- GET /workflows/{workflow_id}/executions
- GET /executions/{execution_id}

### Recovery
- POST /executions/{execution_id}/recovery-plans
- GET /executions/{execution_id}/recovery-plans
- GET /recovery-plans/{plan_id}
- GET /recovery-plans/{plan_id}/conflicts
- POST /recovery-plans/{plan_id}/approve
- POST /recovery-plans/{plan_id}/reject
- POST /recovery-plans/{plan_id}/execute
- GET /recovery-plans/{plan_id}/execution-status

### Audit
- GET /api/v1/audit-events
- GET /api/v1/audit-events/{event_id}
- GET /api/v1/executions/{execution_id}/audit-events
- GET /api/v1/recovery-plans/{plan_id}/audit-events

## 4. User Roles

### ADMIN
Administrative access.

### OPERATOR
Workflow creation, execution and recovery operations.

### VIEWER
Read-only workspace access.

Audit history is restricted to ADMIN and OPERATOR by the backend.

## 5. Environment Configuration

Use backend/.env.example as a reference for the backend environment variables.

IMPORTANT:
The current backend config.py reads operating-system environment variables
using os.getenv. It does not automatically load a .env file.

Do not put real database passwords or production secrets in this example file.

Before production deployment:
- Generate a strong SECRET_KEY.
- Configure secure database credentials.
- Set ENVIRONMENT=production.
- Configure the production frontend API URL.
- Configure backend CORS for the actual frontend origin.

The frontend/.env.example file documents VITE_API_BASE_URL.
An empty value uses the configured Vite development proxy.

## 6. Important Implementation Limitations

The current execution service simulates workflow step execution.

The current recovery executor simulates recovery actions.

Real external business services and APIs have not yet been integrated.

Dashboard statistics currently depend on the records returned by the configured API pagination limits.

## 7. Planned Deployment

Azure Database for PostgreSQL and production hosting are future deployment tasks.
Local development configuration does not mean Azure deployment is complete.

## 8. Testing

Run the consolidated frontend and backend test session after implementation is complete.
