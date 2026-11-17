# UNDOX - Final Development Status

## Implemented Frontend Modules

- Authentication context
- Login and registration screens
- Dashboard data service and context
- Workflow listing and builder
- Ordered workflow steps
- JSON input payload configuration
- Compensation payload configuration
- Execution Center
- Failure simulation interface
- Execution history and step details
- Recovery Center
- Conflict inspection
- Recovery approval and rejection
- Manual review acknowledgement
- Recovery execution progress
- Audit Center and filters
- Profile information
- Logout functionality
- Role-based frontend restrictions

## Backend Integration

Frontend API functions have been configured for the routes
identified in the FastAPI source files.

Actual connectivity and response compatibility still require
the consolidated testing session.

## First Admin Account

Newly registered users receive the default VIEWER role.

After registering the account, configure the required database
environment variables and run the following command from backend:

python -m app.promote_admin your-email@example.com

This promotes only the specified existing user to ADMIN.

## Known Limitations

1. Workflow execution currently simulates step execution.
2. Recovery execution currently simulates recovery actions.
3. Real external business services are not connected.
4. Dashboard execution and recovery totals use data fetched
   through the available API pagination limits.
5. Azure deployment has not yet been completed.
6. Production secrets, database credentials, CORS and hosting
   configuration must be configured before deployment.

## Remaining Work

- Consolidated frontend and backend testing
- Database and migration verification
- API request and response corrections, if required
- Authentication and role permission verification
- Workflow execution and recovery end-to-end verification
- UI fixes discovered during testing
- Optional Azure deployment
