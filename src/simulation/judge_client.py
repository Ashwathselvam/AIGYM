"""
Judge client for the Solution Runner API.

This module provides a client for the Solution Runner API, allowing the Judge
to run solutions in isolated containers without directly using Docker.
"""
import os
import uuid
import time
import logging
import requests
import websockets
import asyncio
import json
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SolutionRunnerClient:
    """Client for the Solution Runner API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize the client with the API base URL."""
        self.base_url = base_url or os.environ.get("SOLUTION_RUNNER_API_URL", "http://solution-runner-api:8080")
        self.ws_url = self.base_url.replace('http', 'ws') + '/ws'
        self.health_check()
    
    def health_check(self) -> bool:
        """Check if the Solution Runner API is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            status = response.json()
            if status.get("status") == "healthy":
                logger.info("Solution Runner API is healthy")
                return True
            else:
                logger.warning(f"Solution Runner API is unhealthy: {status}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to Solution Runner API: {e}")
            return False
    
    def run_solution(
        self,
        code: str,
        language: str = "python",
        memory_limit_mb: int = 128,
        time_limit_sec: int = 10,
        solution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a solution and wait for the results.
        
        Args:
            code: The solution code to run
            language: The programming language (python, javascript, java, etc.)
            memory_limit_mb: Memory limit in MB
            time_limit_sec: Time limit in seconds
            solution_id: Optional unique identifier for the solution
            
        Returns:
            Dictionary with solution results (status, exit_code, logs, execution_time_ms)
        """
        solution_id = solution_id or str(uuid.uuid4())
        
        # Prepare request data
        data = {
            "solution_id": solution_id,
            "code": code,
            "language": language,
            "memory_limit_mb": memory_limit_mb,
            "time_limit_sec": time_limit_sec,
            "network_disabled": True
        }
        
        try:
            # Submit solution
            response = requests.post(f"{self.base_url}/solutions", json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            # If solution is still running, poll for results
            if result.get("status") == "running":
                return self._poll_solution_status(solution_id, time_limit_sec)
            
            return result
        except Exception as e:
            logger.error(f"Error running solution {solution_id}: {e}")
            return {
                "solution_id": solution_id,
                "status": "error",
                "error": str(e)
            }
    
    def _poll_solution_status(self, solution_id: str, timeout_sec: int = 10) -> Dict[str, Any]:
        """
        Poll for solution status until completion or timeout.
        
        Args:
            solution_id: The solution ID to poll
            timeout_sec: Maximum time to wait in seconds
            
        Returns:
            Dictionary with solution results
        """
        start_time = time.time()
        poll_interval = 0.5  # Start with 500ms between polls
        
        while time.time() - start_time < timeout_sec + 5:
            try:
                response = requests.get(f"{self.base_url}/solutions/{solution_id}", timeout=5)
                response.raise_for_status()
                result = response.json()
                
                # If solution is completed or errored, return results
                if result.get("status") in ["completed", "error"]:
                    return result
                
                # Exponential backoff for polling (up to 2 seconds between polls)
                poll_interval = min(poll_interval * 1.5, 2.0)
                time.sleep(poll_interval)
            except Exception as e:
                logger.error(f"Error polling solution status for {solution_id}: {e}")
                return {
                    "solution_id": solution_id,
                    "status": "error",
                    "error": str(e)
                }
        
        # Timeout reached, try to stop the solution
        try:
            requests.delete(f"{self.base_url}/solutions/{solution_id}", timeout=5)
        except:
            pass
        
        return {
            "solution_id": solution_id,
            "status": "timeout",
            "error": f"Solution execution timed out after {timeout_sec} seconds"
        }
    
    def stop_solution(self, solution_id: str) -> Dict[str, Any]:
        """
        Stop a running solution.
        
        Args:
            solution_id: The solution ID to stop
            
        Returns:
            Dictionary with status of the stop operation
        """
        try:
            response = requests.delete(f"{self.base_url}/solutions/{solution_id}", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error stopping solution {solution_id}: {e}")
            return {
                "solution_id": solution_id,
                "status": "error",
                "error": str(e)
            }

    async def get_solution_result(self, solution_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Get the result of a solution using WebSocket.
        
        Args:
            solution_id: Unique identifier for the solution
            timeout: Maximum time to wait for result in seconds
            
        Returns:
            Dict containing the solution result, or None if not found
        """
        try:
            async with websockets.connect(f"{self.ws_url}/solutions/{solution_id}") as websocket:
                # Wait for the result with timeout
                try:
                    result = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    return json.loads(result)
                except asyncio.TimeoutError:
                    logger.error(f"Timeout waiting for solution result: {solution_id}")
                    return None
                except Exception as e:
                    logger.error(f"Error receiving solution result: {e}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return None 