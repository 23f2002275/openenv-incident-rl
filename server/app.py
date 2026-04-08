"""
FastAPI server for the Incident Report Structuring Environment.
"""

from openenv.core.env_server import create_app

import sys, os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from server.incident_environment import IncidentEnvironment

from models import IncidentAction, IncidentObservation

app = create_app(
    IncidentEnvironment,
    IncidentAction,
    IncidentObservation,
    max_concurrent_envs=10,
)

from fastapi.responses import JSONResponse
from tasks import TASKS

app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/metadata"]

@app.get("/metadata", include_in_schema=False)
async def metadata_override():
    return JSONResponse({
        "name": "incident_report_structuring",
        "description": "Extract structured data from messy IT incident reports. 9 tasks with graders across easy/medium/hard difficulty.",
        "version": "1.0.0",
        "author": "Tensors team",
        "documentation_url": None,
        "readme_content": None,
        "num_tasks": len(TASKS),
        "tasks_with_graders": len(TASKS),
        "tasks": [
            {
                "id": t["id"],
                "difficulty": t["difficulty"],
                "description": t["description"],
                "has_grader": True,
                "num_fields": len(t["fields_to_extract"]),
            }
            for t in TASKS
        ],
    })

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/tasks")
def list_tasks():
    from tasks import TASKS
    return {
        "tasks": [
            {
                "id": t["id"],
                "difficulty": t["difficulty"],
                "description": t["description"],
                "has_grader": True,
                "fields_count": len(t["fields_to_extract"])
            }
            for t in TASKS
        ],
        "total": len(TASKS)
    }

@app.post("/tasks/{task_id}/grade")
def grade_task(task_id: str, action: dict):
    from tasks import get_task_by_id
    from grader import grade_extraction
    task = get_task_by_id(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, 
                          detail=f"Task {task_id} not found")
    extracted = action.get("extracted_data", {})
    result = grade_extraction(
        extracted_data=extracted,
        ground_truth=task["ground_truth"],
        field_types=task["field_types"]
    )
    return {
        "task_id": task_id,
        "reward": result["reward"],
        "fields_correct": result["fields_correct"],
        "fields_total": result["fields_total"],
        "field_scores": result["field_scores"]
    }

def main():
    """Entry point for running the server directly."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()