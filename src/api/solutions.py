"""
API endpoints for solution submission and evaluation.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, UUID4
from typing import Optional, Dict, Any, List
import asyncio
from uuid import uuid4
import logging
import json

from db.core import get_conn
from simulation.judge import Judge

router = APIRouter(prefix="/solutions", tags=["solutions"])

# Initialize the judge service
judge = Judge()

class SolutionSubmission(BaseModel):
    """Solution submission model."""
    episode_id: UUID4
    task_id: str
    content: str  # The solution code or content


class SolutionResult(BaseModel):
    """Result of a solution evaluation."""
    episode_id: UUID4
    task_id: str
    success: bool
    score: float
    metrics: Dict[str, Any] = {}
    feedback: List[Dict[str, Any]] = []


@router.post("", response_model=SolutionResult)
async def submit_solution(submission: SolutionSubmission):
    """Submit a solution for evaluation."""
    try:
        # Evaluate the solution using the judge service
        result = await judge.evaluate_solution(
            episode_id=submission.episode_id,
            task_id=submission.task_id,
            solution_code=submission.content
        )
        
        # Return the result
        return SolutionResult(
            episode_id=result.episode_id,
            task_id=result.task_id,
            success=result.success,
            score=result.score,
            metrics=result.metrics,
            feedback=result.feedback
        )
        
    except ValueError as e:
        # Task spec not found or other validation error
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Unexpected error
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/{episode_id}", response_model=SolutionResult)
async def get_solution_result(episode_id: UUID4):
    """Get the result of a previously evaluated solution."""
    logger = logging.getLogger("api.solutions")
    
    try:
        # Get the solution result from the database
        logger.info(f"Retrieving solution result for episode_id: {episode_id}")
        
        # Use the connection context manager properly
        with get_conn() as conn:
            # Get episode data
            logger.info("Executing SQL query to get episode data")
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT e.episode_id, e.task_id, e.success, e.score, e.metrics
                       FROM episodes e
                       WHERE e.episode_id = %s""",
                    (str(episode_id),)
                )
                
                result = cur.fetchone()
                logger.info(f"Query result: {result}")
                
                if not result:
                    logger.warning(f"Solution result not found for episode_id: {episode_id}")
                    raise HTTPException(status_code=404, detail="Solution result not found")
                
                # Get feedback for this episode
                logger.info("Executing SQL query to get feedback data")
                cur.execute(
                    """SELECT source, rating, rationale, rubric_section
                       FROM feedback
                       WHERE episode_id = %s""",
                    (str(episode_id),)
                )
                
                feedback = []
                for row in cur.fetchall():
                    feedback.append({
                        "source": row[0],
                        "rating": row[1],
                        "rationale": row[2],
                        "rubric_section": row[3]
                    })
                
                logger.info(f"Found {len(feedback)} feedback items")
                
                # Convert UUID to string if needed
                episode_id_value = str(result[0]) if result[0] else None
                task_id_value = result[1] if result[1] else "unknown"
                
                # Handle NULL values in the database with defaults
                success_value = False if result[2] is None else result[2]
                score_value = 0.0 if result[3] is None else result[3]
                metrics_value = {} if result[4] is None else result[4]
                
                # Return the result
                return SolutionResult(
                    episode_id=episode_id_value,
                    task_id=task_id_value,
                    success=success_value,
                    score=score_value,
                    metrics=metrics_value,
                    feedback=feedback
                )
            
    except HTTPException:
        raise
        
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error retrieving solution result: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Unexpected error
        raise HTTPException(status_code=500, detail=f"Failed to retrieve result: {str(e)}") 