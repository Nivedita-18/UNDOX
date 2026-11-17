# UNDOX
## Workflow Failure Recovery System

UNDOX is a workflow management and failure recovery platform
built with React, FastAPI, SQLAlchemy and PostgreSQL.

The platform supports sequential workflow definitions,
execution monitoring, simulated failures, recovery planning,
conflict inspection, approval workflows and audit history.

---

## 1. Technology Stack

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
- Alembic
- PostgreSQL
- JWT Authentication
- Argon2 Password Hashing

---

## 2. Main Features

1. User Registration and Login
2. JWT Authentication
3. Role-based Access Control
4. Workflow Creation
5. Ordered Workflow Steps
6. JSON Input Payload Configuration
7. Compensation Payload Configuration
8. Workflow Execution
9. Failure Simulation
10. Execution History
11. Recovery Plan Generation
12. Recovery Conflict Inspection
13. Manual Review Acknowledgement
14. Recovery Approval and Rejection
15. Recovery Execution
16. Audit Event History
17. User Profile and Logout

---

## 3. Project Structure

UNDOX/
|
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- auth/
|   |   |-- audit/
|   |   |-- executions/
|   |   |-- models/
|   |   |-- recovery/
|   |   |-- schemas/
|   |   |-- workflows/
|   |   |-- config.py
|   |   |-- database.py
|   |   |-- main.py
|   |   |-- promote_admin.py
|   |
|   |-- alembic/
|   |-- requirements.txt
|   |-- alembic.ini
|   |-- .env.example
|
|-- frontend/
|   |-- src/
|   |   |-- api/
|   |   |-- components/
|   |   |-- context/
|   |   |-- pages/
|   |   |-- services/
|   |   |-- App.jsx
|   |   |-- App.css
|   |   |-- AppGate.jsx
|   |   |-- main.jsx
|   |
|   |-- package.json
|   |-- vite.config.js
|   |-- .env.example
|
|-- .gitignore
|-- DEVELOPMENT_GUIDE.md
|-- FINAL_PROJECT_STATUS.md
|-- README.md

---

## 4. Database

Database: PostgreSQL

Database name: undox_dev

Main database entities:

- users
- workflow_instances
- workflow_steps
- workflow_executions
- execution_steps
- recovery_plans
- recovery_plan_actions
- audit_events

Database configuration is managed through environment variables.

---

## 5. Backend API Endpoints

### Authentication
POST /auth/register
POST /auth/login
GET  /auth/me

### Workflows
POST /workflows
GET  /workflows
GET  /workflows/{workflow_id}

### Executions
POST /workflows/{workflow_id}/execute
GET  /workflows/{workflow_id}/executions
GET  /executions/{execution_id}

### Recovery
POST /executions/{execution_id}/recovery-plans
GET  /executions/{execution_id}/recovery-plans
GET  /recovery-plans/{plan_id}
GET  /recovery-plans/{plan_id}/conflicts
POST /recovery-plans/{plan_id}/approve
POST /recovery-plans/{plan_id}/reject
POST /recovery-plans/{plan_id}/execute
GET  /recovery-plans/{plan_id}/execution-status

### Audit
GET /api/v1/audit-events
GET /api/v1/audit-events/{event_id}
GET /api/v1/executions/{execution_id}/audit-events
GET /api/v1/recovery-plans/{plan_id}/audit-events

### Health
GET /
GET /health
GET /health/db

---

## 6. User Roles

### ADMIN
Administrative access to the platform.

### OPERATOR
Can create workflows, execute operations and manage recovery plans.

### VIEWER
Read-only access to permitted workspace resources.

Audit history is restricted to ADMIN and OPERATOR by the backend.

---

## 7. Local Setup

### Backend

Open PowerShell at the project root.

Activate the existing virtual environment:

    .\.venv\Scripts\Activate.ps1

Configure your PostgreSQL credentials in the PowerShell session.
Do not commit passwords or production secrets to Git.

Set the backend environment:

    $env:ENVIRONMENT = "development"
    $env:DEBUG = "true"
    $env:DB_USER = "postgres"
    $env:DB_HOST = "localhost"
    $env:DB_PORT = "5432"
    $env:DB_NAME = "undox_dev"

Set DB_PASSWORD securely in the local environment.

Install dependencies:

    pip install -r backend/requirements.txt

Apply database migrations from the backend directory:

    cd backend
    alembic upgrade head

Start the backend:

    python -m uvicorn app.main:app --reload

Backend API documentation:

    http://127.0.0.1:8000/docs

### Frontend

Open a separate terminal:

    cd frontend

Install dependencies:

    npm install

Start the Vite development server:

    npm run dev

The Vite development proxy forwards API requests to:

    http://127.0.0.1:8000

---

## 8. Initial Admin Account

Newly registered users receive the default VIEWER role.

After registering the account, run this command from the backend directory:

    python -m app.promote_admin your-email@example.com

This promotes the selected existing user to ADMIN.

---

## 9. Security Notes

- Never commit actual database passwords.
- Never commit production JWT secrets.
- Use a strong SECRET_KEY in production.
- Configure production CORS explicitly.
- Use HTTPS in production.
- Keep database credentials outside source control.
- Backend role enforcement remains authoritative.

---

## 10. Known Limitations

The current backend execution engine simulates workflow steps.

The recovery executor simulates recovery actions.

Real external services, payment systems, inventory systems
and third-party APIs have not yet been integrated.

Dashboard totals depend on available paginated API results.

Azure Database for PostgreSQL and production hosting
are planned deployment tasks, not completed deployments.

---

## 11. Project Status

Frontend modules and API integration code have been
implemented as the initial local development version.

The application still requires consolidated verification
of imports, runtime behavior, database migrations,
authentication, API contracts and end-to-end workflows.

Refer to FINAL_PROJECT_STATUS.md for the development checklist.
