"""
Trainer service for fine-tuning LLMs based on judge feedback.

This module runs as a standalone service that:
1. Periodically checks for new high-quality episodes with judge feedback
2. Creates training datasets from these episodes
3. Fine-tunes the LLM model
4. Saves the model for inference use
"""
import time
import logging
import os
from datetime import datetime, timedelta
import uuid

from db.core import get_conn
from models.settings import settings
from workers.llm import ModelTrainer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Training parameters
MIN_TRAINING_EXAMPLES = 10  # Minimum number of examples needed to trigger training
TRAINING_INTERVAL_HOURS = 24  # How often to check for new training data
MIN_QUALITY_THRESHOLD = 0.7  # Minimum quality score for training examples


def get_eligible_episodes(threshold=MIN_QUALITY_THRESHOLD, 
                          hours=TRAINING_INTERVAL_HOURS,
                          min_examples=MIN_TRAINING_EXAMPLES):
    """
    Find episodes that are eligible for model training.
    
    Args:
        threshold: Minimum quality score for episodes
        hours: Look back period in hours
        min_examples: Minimum number of examples needed
        
    Returns:
        list of episode IDs if enough found, empty list otherwise
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Find episodes with high-quality judge feedback
            cur.execute(
                """SELECT e.episode_id 
                   FROM episodes e
                   JOIN feedback f ON e.episode_id = f.episode_id
                   WHERE f.source = 'judge'
                   AND f.rating >= %s
                   AND e.started_at >= %s
                   AND e.episode_id NOT IN (
                       SELECT episode_id FROM model_training_history
                   )
                   GROUP BY e.episode_id
                   HAVING COUNT(f.feedback_id) > 0
                   LIMIT 500""",
                (threshold, datetime.now() - timedelta(hours=hours))
            )
            
            episode_ids = [str(row[0]) for row in cur.fetchall()]
            
            logger.info(f"Found {len(episode_ids)} eligible episodes for training")
            
            # Return the IDs if we have enough, otherwise empty list
            return episode_ids if len(episode_ids) >= min_examples else []


def record_training(episode_ids, model_path, metrics):
    """
    Record that these episodes were used for training.
    
    Args:
        episode_ids: List of episode IDs used in training
        model_path: Path to the trained model
        metrics: Dictionary of training metrics
    """
    training_id = str(uuid.uuid4())
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Create training record
            cur.execute(
                """INSERT INTO model_training (
                       training_id, model_path, num_examples, 
                       created_at, metrics
                   ) VALUES (%s, %s, %s, %s, %s)""",
                (
                    training_id,
                    model_path,
                    len(episode_ids),
                    datetime.now(),
                    metrics
                )
            )
            
            # Record which episodes were used
            for episode_id in episode_ids:
                cur.execute(
                    """INSERT INTO model_training_history (
                           training_id, episode_id
                       ) VALUES (%s, %s)""",
                    (training_id, episode_id)
                )
                
            conn.commit()


def migrate_tables():
    """Create tables needed for training history if they don't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS model_training (
                    training_id UUID PRIMARY KEY,
                    model_path TEXT NOT NULL,
                    num_examples INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    metrics JSONB
                );
                
                CREATE TABLE IF NOT EXISTS model_training_history (
                    id SERIAL PRIMARY KEY,
                    training_id UUID NOT NULL REFERENCES model_training(training_id),
                    episode_id UUID NOT NULL REFERENCES episodes(episode_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_training_history_episode 
                ON model_training_history(episode_id);
            """)
            conn.commit()


def main():
    """Main entry point for the trainer service."""
    logger.info("Starting LLM Trainer Service")
    
    # Create necessary tables
    migrate_tables()
    
    while True:
        try:
            # Find eligible episodes
            episode_ids = get_eligible_episodes()
            
            if episode_ids:
                logger.info(f"Starting training run with {len(episode_ids)} episodes")
                
                # Initialize trainer
                trainer = ModelTrainer(
                    model_name=settings.llm_model_name,
                    output_dir=settings.models_dir
                )
                
                # Prepare training data
                training_data = trainer.prepare_training_data(episode_ids)
                
                if training_data:
                    # Train the model
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_dir = os.path.join(settings.models_dir, f"model_{timestamp}")
                    
                    output_path = trainer.fine_tune(
                        training_data=training_data,
                        epochs=3,
                        batch_size=4
                    )
                    
                    # Record training in database
                    metrics = {
                        "examples_count": len(training_data),
                        "model_base": settings.llm_model_name,
                        "epochs": 3
                    }
                    
                    record_training(episode_ids, output_path, metrics)
                    
                    logger.info(f"Training complete. Model saved to {output_path}")
                else:
                    logger.warning("No usable training data found in eligible episodes")
            
            # Wait for next check
            logger.info(f"Waiting {TRAINING_INTERVAL_HOURS} hours until next training check")
            time.sleep(TRAINING_INTERVAL_HOURS * 3600)
            
        except Exception as e:
            logger.error(f"Error in training loop: {e}")
            # Wait a bit before trying again
            time.sleep(900)  # 15 minutes


if __name__ == "__main__":
    main() 