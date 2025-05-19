#!/usr/bin/env python3
"""
Test that verifies if solution evaluation results are properly stored in the database.
"""
import requests
import json
import time
import uuid
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_URL = "http://localhost:8000"
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'example',
    'dbname': 'aigym'
}

# Sample solution that should pass
BUBBLE_SORT_SOLUTION = """
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

def create_episode():
    """Create a new episode for testing"""
    payload = {
        "task_id": "sorting_001",
        "task_version": "v1",
        "rubric_version": "v1.0",
        "content": "Test episode for bubble sort task"
    }
    
    try:
        logger.info(f"Creating episode with payload: {payload}")
        response = requests.post(f"{API_URL}/episodes", json=payload)
        response.raise_for_status()
        data = response.json()
        episode_id = data.get('episode_id')
        if not episode_id:
            logger.error("❌ Episode creation failed: no episode ID returned")
            logger.error(f"Response: {data}")
            return None
        logger.info(f"Episode created successfully with ID: {episode_id}")
        
        # Add a delay to allow the API to process the request
        time.sleep(2)
        
        # Try to verify the episode was stored, but continue even if this fails
        try:
            # Verify the episode was stored in the database using the returned episode_id
            response = requests.get(f"{API_URL}/episodes/{episode_id}")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Retrieved episode: {data}")
        except Exception as e:
            logger.warning(f"Could not retrieve episode after creation: {e}")
            logger.warning("Continuing with test anyway...")
            
        return episode_id
    except Exception as e:
        logger.error(f"❌ Episode creation failed with exception: {e}")
        return None

def submit_solution(episode_id):
    """Submit a solution for evaluation"""
    payload = {
        "episode_id": episode_id,
        "task_id": "sorting_001",
        "content": BUBBLE_SORT_SOLUTION
    }
    
    try:
        logger.info(f"Submitting solution for episode: {episode_id}")
        response = requests.post(f"{API_URL}/solutions", json=payload)
        
        if response.status_code != 200:
            logger.error(f"Error submitting solution: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
        result = response.json()
        
        logger.info(f"✅ Solution submitted successfully.")
        logger.info(f"  Success: {result.get('success')}, Score: {result.get('score')}")
        logger.info(f"  Metrics: {result.get('metrics')}")
        if result.get('feedback'):
            logger.info(f"  Feedback: {len(result.get('feedback'))} items")
            
        return result
    except Exception as e:
        logger.error(f"❌ Solution submission failed with exception: {e}")
        return None

def check_database(episode_id):
    """Check if the results were properly stored in the database"""
    # Wait a moment for the database update to complete
    time.sleep(2)
    
    try:
        logger.info(f"Connecting to database...")
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dbname=DB_CONFIG['dbname']
        )
        
        with conn.cursor() as cur:
            # Check episodes table
            logger.info(f"Querying database for episode: {episode_id}")
            cur.execute(
                """SELECT success, score, metrics FROM episodes WHERE episode_id = %s""",
                (episode_id,)
            )
            
            episode_result = cur.fetchone()
            if episode_result:
                success, score, metrics = episode_result
                logger.info("\nDatabase check:")
                logger.info(f"  Episodes table success: {success}")
                logger.info(f"  Episodes table score: {score}")
                logger.info(f"  Episodes table metrics: {metrics}")
                
                if success is None:
                    logger.error("❌ Episodes table update FAILED - success is NULL")
                else:
                    logger.info("✅ Episodes table update SUCCESS")
            else:
                logger.error("❌ Episode not found in database")
                
            # Check feedback table
            cur.execute(
                """SELECT COUNT(*) FROM feedback WHERE episode_id = %s""",
                (episode_id,)
            )
            
            feedback_count = cur.fetchone()[0]
            logger.info(f"  Feedback entries in database: {feedback_count}")
            
            if feedback_count > 0:
                logger.info("✅ Feedback entries stored successfully")
            else:
                logger.error("❌ No feedback entries found in database")
                
        conn.close()
    except Exception as e:
        logger.error(f"❌ Database check failed with exception: {e}")

def main():
    """Run the test"""
    logger.info("Starting database storage test...")
    
    # Create episode
    episode_id = create_episode()
    if not episode_id:
        return
    
    # Submit solution
    submit_solution(episode_id)
    
    # Check database
    check_database(episode_id)

if __name__ == "__main__":
    main() 