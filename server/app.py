"""
FastAPI server for the Incident Report Structuring Environment.
"""

from openenv.core.env_server import create_app

import sys, os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from server.incident_environment import IncidentEnvironment

try:
    from models import IncidentAction, IncidentObservation
except ImportError:
    from server.models import IncidentAction, IncidentObservation

app = create_app(
    IncidentEnvironment,
    IncidentAction,
    IncidentObservation,
    max_concurrent_envs=10,
)

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