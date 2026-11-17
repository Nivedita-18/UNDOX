
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status
)

from sqlalchemy.orm import Session

from ..database import get_db

from ..schemas.workflow import (
    WorkflowCreate,
    WorkflowRead
)

from ..workflows import service

from ..auth.dependencies import (
    get_current_user,
    require_roles
)


router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"]
)


# Create workflow - ADMIN and OPERATOR
@router.post(
    "",
    response_model=WorkflowRead,
    status_code=status.HTTP_201_CREATED
)
def create_workflow(
    workflow_data: WorkflowCreate,
    current_user=Depends(
        require_roles("ADMIN", "OPERATOR")
    ),
    db: Session = Depends(get_db)
):

    return service.create_workflow(
        db,
        workflow_data,
        created_by=current_user.id
    )


# List workflows - authenticated users
@router.get(
    "",
    response_model=list[WorkflowRead]
)
def list_workflows(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return service.list_workflows(
        db,
        limit,
        offset
    )


# Get workflow by ID - authenticated users
@router.get(
    "/{workflow_id}",
    response_model=WorkflowRead
)
def get_workflow(
    workflow_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    workflow = service.get_workflow(
        db,
        workflow_id
    )

    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found"
        )

    return workflow
