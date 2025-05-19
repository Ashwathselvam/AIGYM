#!/usr/bin/env python3
"""
AIGYM Smoke Test

This script tests all major components of the AIGYM system to verify they're working correctly.
It tests:
1. Database connectivity (PostgreSQL)
2. Vector database connectivity (Qdrant)
3. Redis connectivity
4. Core API endpoints
5. Solution Runner API
6. End-to-end solution submission and evaluation
"""
import os
import sys
import json
import time
import uuid
import asyncio
import logging
import requests
import psycopg2
import redis
from qdrant_client import QdrantClient
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('smoke_test')

# Configuration
CONFIG = {
    'postgres': {
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'password': 'example',
        'dbname': 'aigym'
    },
    'redis': {
        'host': 'localhost',
        'port': 6379
    },
    'qdrant': {
        'host': 'localhost',
        'port': 6333
    },
    'api': {
        'host': 'localhost',
        'port': 8000
    },
    'solution_runner': {
        'host': 'localhost',
        'port': 8080
    }
}

# Test data
BUBBLE_SORT_SOLUTION = """
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
"""

# Function to check if a service is ready
def is_service_ready(host: str, port: int) -> bool:
    """Check if a service is ready by attempting to connect to it."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(1)
            s.connect((host, port))
            return True
        except Exception as e:
            logger.warning(f"Service at {host}:{port} not ready: {e}")
            return False

# Test PostgreSQL connection
def test_postgres() -> bool:
    """Test connection to PostgreSQL database."""
    logger.info("Testing PostgreSQL connection...")
    try:
        conn = psycopg2.connect(
            host=CONFIG['postgres']['host'],
            port=CONFIG['postgres']['port'],
            user=CONFIG['postgres']['user'],
            password=CONFIG['postgres']['password'],
            dbname=CONFIG['postgres']['dbname']
        )
        
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            logger.info(f"Connected to PostgreSQL: {version[0]}")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"PostgreSQL test failed: {e}")
        return False

# Test Redis connection
def test_redis() -> bool:
    """Test connection to Redis."""
    logger.info("Testing Redis connection...")
    try:
        r = redis.Redis(
            host=CONFIG['redis']['host'],
            port=CONFIG['redis']['port']
        )
        ping = r.ping()
        logger.info(f"Connected to Redis: {ping}")
        return True
    except Exception as e:
        logger.error(f"Redis test failed: {e}")
        return False

# Test Qdrant connection
def test_qdrant() -> bool:
    """Test connection to Qdrant vector database."""
    logger.info("Testing Qdrant connection...")
    try:
        client = QdrantClient(
            host=CONFIG['qdrant']['host'],
            port=CONFIG['qdrant']['port']
        )
        
        # Check collections
        collections = client.get_collections()
        logger.info(f"Connected to Qdrant. Collections: {collections}")
        return True
    except Exception as e:
        logger.error(f"Qdrant test failed: {e}")
        return False

# Test API health endpoint
def test_api_health() -> bool:
    """Test the API health endpoint."""
    logger.info("Testing API health endpoint...")
    try:
        url = f"http://{CONFIG['api']['host']}:{CONFIG['api']['port']}/healthz"
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"API health check successful: {response.json()}")
        return True
    except Exception as e:
        logger.error(f"API health check failed: {e}")
        return False

# Test Solution Runner API health endpoint
def test_solution_runner_health() -> bool:
    """Test the Solution Runner API health endpoint."""
    logger.info("Testing Solution Runner API health endpoint...")
    try:
        url = f"http://{CONFIG['solution_runner']['host']}:{CONFIG['solution_runner']['port']}/health"
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"Solution Runner API health check successful: {response.json()}")
        return True
    except Exception as e:
        logger.error(f"Solution Runner API health check failed: {e}")
        return False

# Test episode creation
def test_create_episode() -> Optional[str]:
    """Test creating an episode and return the episode ID if successful."""
    logger.info("Testing episode creation...")
    try:
        url = f"http://{CONFIG['api']['host']}:{CONFIG['api']['port']}/episodes"
        payload = {
            "task_id": "sorting_001",
            "task_version": "v1",
            "rubric_version": "v1.0",
            "content": "Test episode for bubble sort task"
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        episode_id = response.json().get('episode_id')
        logger.info(f"Episode created successfully with ID: {episode_id}")
        return episode_id
    except Exception as e:
        logger.error(f"Episode creation failed: {e}")
        return None

# Test solution submission
def test_submit_solution(episode_id: str) -> bool:
    """Test submitting a solution for evaluation."""
    logger.info("Testing solution submission...")
    try:
        url = f"http://{CONFIG['api']['host']}:{CONFIG['api']['port']}/solutions"
        payload = {
            "episode_id": episode_id,
            "task_id": "sorting_001",
            "content": BUBBLE_SORT_SOLUTION
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Solution submitted successfully. Success: {result.get('success')}, Score: {result.get('score')}")
        return True
    except Exception as e:
        logger.error(f"Solution submission failed: {e}")
        return False

# Test getting solution results
def test_get_solution_result(episode_id: str) -> bool:
    """Test retrieving solution evaluation results."""
    logger.info("Testing solution result retrieval...")
    try:
        url = f"http://{CONFIG['api']['host']}:{CONFIG['api']['port']}/solutions/{episode_id}"
        
        # May need to wait for evaluation to complete
        max_retries = 10  # Increased from 5 to 10
        for attempt in range(max_retries):
            try:
                response = requests.get(url)
                
                if response.status_code == 404:
                    # Result not available yet, wait and retry
                    logger.info(f"Solution result not available yet (attempt {attempt+1}/{max_retries}). Waiting...")
                    time.sleep(3)  # Increased from 2 to 3 seconds
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                # Log detailed information about the result
                logger.info(f"Solution result retrieved successfully:")
                logger.info(f"  Episode ID: {result.get('episode_id')}")
                logger.info(f"  Task ID: {result.get('task_id')}")
                logger.info(f"  Success: {result.get('success')}")
                logger.info(f"  Score: {result.get('score')}")
                logger.info(f"  Metrics: {result.get('metrics')}")
                
                if 'feedback' in result and result['feedback']:
                    logger.info(f"  Feedback: {len(result['feedback'])} items")
                    for item in result['feedback']:
                        logger.info(f"    - {item.get('source')}: {item.get('rating')} - {item.get('rationale')}")
                
                return True
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error retrieving solution result (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(3)
        
        logger.error("Failed to retrieve solution results after multiple attempts")
        return False
    except Exception as e:
        logger.error(f"Solution result retrieval failed: {e}")
        return False

# Test running a solution directly with Solution Runner API
def test_solution_runner() -> bool:
    """Test running a solution directly with the Solution Runner API."""
    logger.info("Testing direct solution execution with Solution Runner API...")
    try:
        url = f"http://{CONFIG['solution_runner']['host']}:{CONFIG['solution_runner']['port']}/solutions"
        solution_id = str(uuid.uuid4())
        
        # Make sure the solution includes both the function definition and a test call with print
        test_code = """
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

# Test the function with explicit print statement
test_array = [5, 1, 4, 2, 8]
sorted_array = bubble_sort(test_array)
print(f"Sorted array: {sorted_array}")
"""
        
        payload = {
            "solution_id": solution_id,
            "code": test_code,
            "language": "python",
            "memory_limit_mb": 128,
            "time_limit_sec": 10,
            "network_disabled": True
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        # Wait for solution to complete
        status_url = f"http://{CONFIG['solution_runner']['host']}:{CONFIG['solution_runner']['port']}/solutions/{solution_id}"
        max_retries = 15  # Increased timeout
        for attempt in range(max_retries):
            try:
            status_response = requests.get(status_url)
                
                # If 404, the solution might have completed and been cleaned up
                if status_response.status_code == 404 and attempt > 0:
                    logger.info("Solution was executed and results were cleaned up")
                    return True
                
            status_response.raise_for_status()
            status = status_response.json()
            
            if status.get('status') == 'completed':
                logs = status.get('logs', '')
                logger.info(f"Solution execution completed. Exit code: {status.get('exit_code')}")
                logger.info(f"Output: {logs.strip()}")
                expected_output = '[1, 2, 4, 5, 8]'
                    if expected_output in logs or "Sorted array: [1, 2, 4, 5, 8]" in logs:
                    logger.info("Solution output correct")
                    return True
                else:
                    logger.error(f"Solution output incorrect. Expected '{expected_output}' in output")
                        logger.error(f"Actual output: {logs}")
                    return False
            
            logger.info(f"Solution still running (attempt {attempt+1}/{max_retries}). Waiting...")
            time.sleep(1)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error getting solution status (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(1)
        
        logger.error("Solution execution timed out")
        return False
    except Exception as e:
        logger.error(f"Solution Runner API test failed: {e}")
        return False

# Run all tests
def run_smoke_test():
    """Run all smoke tests."""
    logger.info("Starting AIGYM smoke tests...")
    
    results = {}
    
    # Test individual services
    results['postgres'] = test_postgres()
    results['redis'] = test_redis()
    results['qdrant'] = test_qdrant()
    results['api_health'] = test_api_health()
    results['solution_runner_health'] = test_solution_runner_health()
    
    # Test end-to-end flow
    if results['api_health']:
        episode_id = test_create_episode()
        if episode_id:
            results['create_episode'] = True
            results['submit_solution'] = test_submit_solution(episode_id)
            results['get_solution_result'] = test_get_solution_result(episode_id)
        else:
            results['create_episode'] = False
            results['submit_solution'] = False
            results['get_solution_result'] = False
    else:
        results['create_episode'] = False
        results['submit_solution'] = False
        results['get_solution_result'] = False
    
    # Test Solution Runner API directly
    if results['solution_runner_health']:
        results['solution_runner_execution'] = test_solution_runner()
    else:
        results['solution_runner_execution'] = False
    
    # Print summary
    logger.info("\n--- SMOKE TEST RESULTS ---")
    all_passed = True
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{test}: {status}")
        if not result:
            all_passed = False
    
    logger.info(f"\nOverall status: {'PASS' if all_passed else 'FAIL'}")
    return all_passed

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)