"""
Solution runner API for executing code in isolated containers.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import docker
import asyncio
import logging
import json
from typing import Dict, Any, Optional
import os
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize Docker client
docker_client = docker.from_env()

# Store active solutions and their status
active_solutions: Dict[str, Dict[str, Any]] = {}

class SolutionRequest(BaseModel):
    """Solution execution request."""
    code: str
    language: str
    memory_limit_mb: int
    time_limit_sec: int
    solution_id: str

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/solutions")
async def run_solution(request: SolutionRequest):
    """Run a solution in an isolated container."""
    try:
        # Store solution request
        active_solutions[request.solution_id] = {
            "status": "running",
            "start_time": time.time(),
            "request": request.dict()
        }
        
        # Run solution in background
        asyncio.create_task(execute_solution(request.solution_id))
        
        return {"status": "accepted", "solution_id": request.solution_id}
        
    except Exception as e:
        logger.error(f"Failed to run solution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/solutions/{solution_id}")
async def solution_status(websocket: WebSocket, solution_id: str):
    """WebSocket endpoint for solution status updates."""
    await websocket.accept()
    
    try:
        # Send initial status
        if solution_id in active_solutions:
            await websocket.send_json(active_solutions[solution_id])
        else:
            await websocket.send_json({"status": "not_found"})
            return
            
        # Wait for solution completion
        while True:
            solution = active_solutions.get(solution_id)
            if not solution:
                await websocket.send_json({"status": "not_found"})
                break
                
            if solution["status"] in ["completed", "error", "timeout"]:
                await websocket.send_json(solution)
                break
                
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for solution: {solution_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"status": "error", "error": str(e)})
        except:
            pass

async def execute_solution(solution_id: str):
    """Execute a solution in a container."""
    try:
        solution = active_solutions[solution_id]
        request = solution["request"]
        
        # Create container
        container = docker_client.containers.run(
            image=f"{request['language']}:latest",
            command=["python", "-c", request["code"]],
            mem_limit=f"{request['memory_limit_mb']}m",
            detach=True
        )
        
        # Wait for completion with timeout
        try:
            result = container.wait(timeout=request["time_limit_sec"])
            logs = container.logs().decode()
            
            # Update solution status
            active_solutions[solution_id].update({
                "status": "completed",
                "exit_code": result["StatusCode"],
                "logs": logs,
                "execution_time_ms": (time.time() - solution["start_time"]) * 1000
            })
            
        except Exception as e:
            # Handle timeout or other errors
            active_solutions[solution_id].update({
                "status": "error",
                "error": str(e)
            })
            
        finally:
            # Clean up container
            try:
                container.remove(force=True)
            except:
                pass
            
    except Exception as e:
        logger.error(f"Failed to execute solution: {e}")
        active_solutions[solution_id].update({
            "status": "error",
            "error": str(e)
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 