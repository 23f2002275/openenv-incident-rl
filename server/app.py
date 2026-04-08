"""
FastAPI server for the Incident Report Structuring Environment.
"""

import sys
import os
import yaml
from fastapi.responses import JSONResponse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from openenv.core.env_server import create_app
from server.incident_environment import IncidentEnvironment
from models import IncidentAction, IncidentObservation

app = create_app(
    IncidentEnvironment,
    IncidentAction,
    IncidentObservation,
    max_concurrent_envs=10,
)

# 1. Remove the default empty metadata route
app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/metadata"]

# 2. Force the server to return your EXACT openenv.yaml file as JSON
@app.get("/metadata", include_in_schema=False)
def override_metadata():
    yaml_path = os.path.join(BASE_DIR, "openenv.yaml")
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        return JSONResponse(manifest)
    except Exception as e:
        return JSONResponse({"error": f"Failed to load yaml: {str(e)}"}, status_code=500)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()