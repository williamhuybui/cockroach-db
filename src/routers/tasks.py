"""
API endpoints for follow-up tasks created after a call.

Tasks are created automatically in calls.py (create_tasks_for_call)
when a completed call is saved. This router lets a dashboard list
open tasks and mark them done.
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from api_models import TaskUpdate
from database import (
    get_database_connection,
    get_database_transaction,
)


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)


@router.get("")
async def list_tasks(
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    """
    Return tasks, newest first.

    Pass ?status=open to show only what's still pending on the
    dashboard, or leave it off to see everything.
    """

    if status_filter is None:
        sql = """
            SELECT *
            FROM tasks
            ORDER BY created_at DESC
            LIMIT %s
        """
        parameters = (limit,)
    else:
        sql = """
            SELECT *
            FROM tasks
            WHERE status = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        parameters = (status_filter, limit)

    async with get_database_connection() as connection:
        cursor = await connection.execute(sql, parameters)
        rows = await cursor.fetchall()

    return [dict(row) for row in rows]


@router.patch("/{task_id}")
async def update_task(
    task_id: UUID,
    update: TaskUpdate,
):
    """
    Mark a task done (or reopen it) from the dashboard.
    """

    async with get_database_transaction() as connection:
        cursor = await connection.execute(
            """
            UPDATE tasks
            SET status = %s,
                completed_at = CASE WHEN %s = 'done' THEN now() ELSE NULL END,
                updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (update.status, update.status, task_id),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    return dict(row)