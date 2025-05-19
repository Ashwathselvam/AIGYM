"""
Judge module for evaluating agent solutions.

This module handles:
1. Loading task specifications from YAML files
2. Running solutions in isolated containers
3. Evaluating outputs based on rubrics
4. Returning results with scores, metrics, and feedback
"""
import os
import time
import json
import logging
import yaml
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from pathlib import Path
from uuid import UUID

from models.settings import settings
from db.core import get_conn
from simulation.judge_client import SolutionRunnerClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize solution runner client
solution_runner = SolutionRunnerClient()

class RubricItem(BaseModel):
    """A single item in a task evaluation rubric."""
    description: str
    weight: float
    

class TaskSpec(BaseModel):
    """Task specification loaded from YAML."""
    task_id: str
    category: str
    grade: str
    prompt: str
    version: str
    rubric_version: str
    time_limit_sec: int
    memory_mb: int
    metric: str
    rubric: List[RubricItem]
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'TaskSpec':
        """Load task specification from YAML file."""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)


class JudgeResult(BaseModel):
    """Result of a solution evaluation."""
    episode_id: UUID
    task_id: str
    success: bool
    score: float
    metrics: Dict[str, Any] = Field(default_factory=dict)
    feedback: List[Dict[str, Any]] = Field(default_factory=list)


class Judge:
    """Judge service for evaluating agent solutions."""

    def __init__(self, task_specs_dir: str = '/app/task_specs'):
        """Initialize the judge service.
        
        Args:
            task_specs_dir: Directory containing task specification YAML files.
        """
        self.task_specs_dir = Path(task_specs_dir)
        self.task_specs = {}
        self._load_task_specs()
        
    def _load_task_specs(self) -> None:
        """Load all task specifications from YAML files."""
        spec_files = list(self.task_specs_dir.glob('*.yaml'))
        for spec_file in spec_files:
            try:
                spec = TaskSpec.from_yaml(str(spec_file))
                self.task_specs[spec.task_id] = spec
                logger.info(f"Loaded task spec: {spec.task_id}")
            except Exception as e:
                logger.error(f"Failed to load task spec from {spec_file}: {e}")
        
        logger.info(f"Loaded {len(self.task_specs)} task specifications")
    
    async def evaluate_solution(self, episode_id: UUID, task_id: str, solution_code: str) -> JudgeResult:
        """Evaluate a solution for a given task.
        
        Args:
            episode_id: Unique identifier for the episode
            task_id: Task identifier
            solution_code: Code or content to evaluate
            
        Returns:
            JudgeResult object with evaluation results
        """
        # Get task specification
        spec = self.task_specs.get(task_id)
        if not spec:
            raise ValueError(f"Task specification not found for task_id: {task_id}")
            
        # Prepare for metrics collection
        start_time = time.time()
        metrics = {}
        
        try:
            # Determine language based on task category
            language = self._get_language_for_category(spec.category)
            
            # Run solution using the solution runner API
            result = solution_runner.run_solution(
                code=solution_code,
                language=language,
                memory_limit_mb=spec.memory_mb,
                time_limit_sec=spec.time_limit_sec,
                solution_id=str(episode_id)
            )
            
            # Get solution results using WebSocket
            solution_result = await solution_runner.get_solution_result(str(episode_id))
            if not solution_result:
                raise Exception("Failed to get solution results")
                
            # Extract metrics from result
            exit_code = solution_result.get('exit_code', -1)
            logs = solution_result.get('logs', '')
            metrics['exit_code'] = exit_code
            
            # Check execution time
            execution_time = solution_result.get('execution_time_ms', (time.time() - start_time) * 1000)
            metrics[spec.metric] = execution_time  # Already in ms
            
            # Check for errors
            if solution_result.get('status') in ['error', 'timeout']:
                error_message = solution_result.get('error', 'Unknown error')
                return JudgeResult(
                    episode_id=episode_id,
                    task_id=task_id,
                    success=False,
                    score=0.0,
                    metrics={'error': error_message},
                    feedback=[{
                        'source': 'judge',
                        'rating': 0.0,
                        'rationale': f"Execution error: {error_message}",
                        'rubric_section': 'execution'
                    }]
                )
                
            # Evaluate based on category
            success, score, feedback = self._evaluate_solution(
                spec=spec,
                logs=logs,
                exit_code=exit_code,
                metrics=metrics
            )
            
            # Record evaluation results
            result = JudgeResult(
                episode_id=episode_id,
                task_id=task_id,
                success=success,
                score=score,
                metrics=metrics,
                feedback=feedback
            )
            
            # Store results in database
            await self._store_results(result)
            
            return result
                
        except Exception as e:
            logger.error(f"Error during solution evaluation: {e}")
                
            return JudgeResult(
                episode_id=episode_id,
                task_id=task_id,
                success=False,
                score=0.0,
                metrics={'error': str(e)},
                feedback=[{
                    'source': 'judge',
                    'rating': 0.0,
                    'rationale': f"Execution error: {e}",
                    'rubric_section': 'execution'
                }]
            )
    
    def _get_language_for_category(self, category: str) -> str:
        """Get appropriate language based on task category."""
        languages = {
            'coding': 'python',
            'data_analysis': 'python',
            'writing': 'markdown',
            'decision_making': 'json'
        }
        return languages.get(category, 'python')
    
    def _evaluate_solution(self, spec: TaskSpec, logs: str, exit_code: int, metrics: Dict[str, Any]) -> tuple:
        """Evaluate solution based on rubric and metrics."""
        # Default values
        success = exit_code == 0
        feedback = []
        
        # Apply rubric
        total_score = 0.0
        total_weight = 0.0
        
        for item in spec.rubric:
            # Simplified scoring - would be more sophisticated in real system
            item_score = self._score_rubric_item(item, logs, exit_code, metrics, spec)
            total_score += item_score * item.weight
            total_weight += item.weight
            
            feedback.append({
                'source': 'judge',
                'rating': item_score,
                'rationale': self._generate_feedback(item, item_score),
                'rubric_section': item.description
            })
        
        # Calculate final score
        final_score = total_score / total_weight if total_weight > 0 else 0.0
        
        # Success if score is above threshold (e.g., 0.6)
        success = final_score >= 0.6
        
        return success, final_score, feedback
    
    def _score_rubric_item(self, item: RubricItem, logs: str, exit_code: int, metrics: Dict[str, Any], spec: TaskSpec) -> float:
        """Score a single rubric item based on solution output and metrics."""
        # This is a simplified scoring function
        # In a real system, this would involve more sophisticated checks
        
        description = item.description.lower()
        
        # Check for successful execution
        if "correct" in description or "output" in description:
            # Basic check - did the program run successfully?
            if exit_code != 0:
                return 0.0
            # Check if expected output is in logs (very simplified)
            return 1.0 if "sorted" in logs else 0.0
            
        # Check for performance metrics
        elif "complexity" in description or "performance" in description:
            runtime_ms = metrics.get(spec.metric, float('inf'))
            # Simple scoring based on runtime
            if runtime_ms < 100:
                return 1.0
            elif runtime_ms < 500:
                return 0.7
            elif runtime_ms < 1000:
                return 0.4
            else:
                return 0.1
                
        # Check for code style
        elif "style" in description or "pep8" in description:
            # Simplified - if no style errors in logs
            return 1.0 if "style error" not in logs.lower() else 0.5
            
        # Default scoring
        return 0.5
    
    def _generate_feedback(self, item: RubricItem, score: float) -> str:
        """Generate feedback text based on rubric item and score."""
        if score > 0.8:
            return f"Excellent work on: {item.description}"
        elif score > 0.6:
            return f"Good job on: {item.description}, but room for improvement"
        elif score > 0.3:
            return f"Needs work on: {item.description}"
        else:
            return f"Failed to meet criteria: {item.description}"
    
    async def _store_results(self, result: JudgeResult) -> None:
        """Store evaluation results in the database."""
        try:
            logger.info(f"Storing evaluation results for episode_id: {result.episode_id}")
            logger.info(f"Results - Success: {result.success}, Score: {result.score}")
            
            # Use the connection context manager properly
            logger.info("Opening database connection")
            with get_conn() as conn:
                # Store main result
                logger.info("Updating episodes table")
                with conn.cursor() as cur:
                    query = """UPDATE episodes 
                               SET success = %s, score = %s, metrics = %s 
                               WHERE episode_id = %s"""
                    params = (
                        result.success,
                        result.score,
                        json.dumps(result.metrics),
                        str(result.episode_id)
                    )
                    logger.info(f"Executing query: {query} with params: {params}")
                    cur.execute(query, params)
                    logger.info(f"Episodes table updated, row count: {cur.rowcount}")
                
                # Store feedback items
                logger.info(f"Storing {len(result.feedback)} feedback items")
                for i, item in enumerate(result.feedback):
                    logger.info(f"Storing feedback item {i+1}: {item}")
                    with conn.cursor() as cur:
                        query = """INSERT INTO feedback 
                                   (episode_id, source, rating, rationale, rubric_section)
                                   VALUES (%s, %s, %s, %s, %s)"""
                        params = (
                            str(result.episode_id),
                            item['source'],
                            item['rating'],
                            item['rationale'],
                            item['rubric_section']
                        )
                        logger.info(f"Executing query: {query} with params: {params}")
                        cur.execute(query, params)
                        logger.info(f"Feedback item inserted, row count: {cur.rowcount}")
                
                # Commit the transaction within the connection context
                logger.info("Committing transaction")
                conn.commit()
                logger.info("Transaction committed successfully")
            
            logger.info("Evaluation results stored successfully")
            
        except Exception as e:
            # Log the full error with traceback for better debugging
            import traceback
            logger.error(f"Failed to store evaluation results: {e}")
            logger.error(traceback.format_exc())


async def main():
    """Main entry point for the judge service."""
    logger.info("Starting Judge service")
    
    # Initialize judge
    judge = Judge()
    
    # TODO: Set up API or message queue consumer to receive evaluation requests
    
    # For development/testing - add a sample task
    # await judge.evaluate_solution(...)
    
    logger.info("Judge service ready")


if __name__ == "__main__":
    asyncio.run(main()) 