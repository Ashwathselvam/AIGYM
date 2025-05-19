"""
Custom LLM implementation using local models (Phi-2/Mistral).
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from tenacity import retry, stop_after_attempt, wait_exponential

from models.settings import settings
from workers.celery_app import celery_app


class LocalLLM:
    """Local LLM implementation using Hugging Face models."""
    
    def __init__(self, model_name=None):
        """Initialize the LLM with a specific model."""
        self.model_name = model_name or settings.llm_model_name
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        
        # Configure model based on GPU availability
        model_kwargs = {
            "device_map": "auto",
            "trust_remote_code": True
        }
        
        # Add GPU-specific settings if enabled
        if settings.use_gpu:
            model_kwargs["torch_dtype"] = torch.float16
        
        # Load the model with appropriate settings
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **model_kwargs
        )
    
    def generate(self, prompt, max_length=1024, temperature=0.7):
        """Generate text using the local model."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, 
                max_length=max_length,
                temperature=temperature,
                top_p=0.9,
                do_sample=temperature > 0
            )
            
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    def embed(self, text):
        """Generate embeddings for the given text."""
        # Use sentence transformers or similar for embeddings
        from sentence_transformers import SentenceTransformer
        
        # Initialize embedding model if not already loaded
        if not hasattr(self, "embedding_model"):
            self.embedding_model = SentenceTransformer(settings.embed_model_name)
            
        # Generate embeddings
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()


# Singleton LLM instance
_llm_instance = None

def get_llm():
    """Get the LLM instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LocalLLM()
    return _llm_instance


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2))
def embed(text: str):
    """Generate embeddings for the given text."""
    llm = get_llm()
    return llm.embed(text)


@celery_app.task(bind=True, retry_backoff=True, max_retries=3)
def chat_completion(self, messages: list[dict]):
    """Generate a chat completion using the local model."""
    llm = get_llm()
    
    # Format messages into a prompt that the model can understand
    prompt = ""
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "system":
            prompt += f"[SYSTEM] {content}\n\n"
        elif role == "user":
            prompt += f"[USER] {content}\n\n"
        elif role == "assistant":
            prompt += f"[ASSISTANT] {content}\n\n"
    
    prompt += "[ASSISTANT]"
    
    # Generate the response
    response = llm.generate(prompt)
    
    # Extract the assistant's response
    assistant_response = response.split("[ASSISTANT]")[-1].strip()
    
    return assistant_response


class ModelTrainer:
    """Trainer for fine-tuning LLMs based on judge feedback."""
    
    def __init__(self, model_name=None, output_dir="./trained_models"):
        """Initialize the model trainer."""
        self.model_name = model_name or settings.llm_model_name
        self.output_dir = output_dir
        
    def prepare_training_data(self, episode_ids):
        """Prepare training data from episodes and judge feedback."""
        from db.core import get_conn
        import json
        
        training_data = []
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Get episodes and their feedback
                cur.execute(
                    """SELECT e.episode_id, e.content, e.task_id, f.rationale, f.rating
                       FROM episodes e
                       JOIN feedback f ON e.episode_id = f.episode_id
                       WHERE e.episode_id IN %s
                       AND f.source = 'judge'""",
                    (tuple(episode_ids),)
                )
                
                for row in cur.fetchall():
                    episode_id, content, task_id, rationale, rating = row
                    
                    # Get task spec
                    cur.execute(
                        """SELECT content FROM episodes 
                           WHERE task_id = %s 
                           LIMIT 1""",
                        (task_id,)
                    )
                    task_spec = cur.fetchone()[0]
                    
                    # Format as a learning example
                    example = {
                        "instruction": task_spec,
                        "input": "",
                        "output": content,
                        "feedback": rationale,
                        "rating": float(rating)
                    }
                    
                    training_data.append(example)
        
        return training_data
        
    def fine_tune(self, training_data, epochs=3, batch_size=4, learning_rate=5e-5):
        """Fine-tune the model using the training data."""
        import os
        from transformers import Trainer, TrainingArguments, DataCollatorForLanguageModeling
        from datasets import Dataset
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load model and tokenizer
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForCausalLM.from_pretrained(self.model_name)
        
        # Format data for training
        formatted_data = []
        for example in training_data:
            # Create prompt with instruction and feedback
            if example["rating"] >= 0.7:  # Use only good examples
                prompt = f"[INSTRUCTION] {example['instruction']}\n\n[RESPONSE] {example['output']}"
                formatted_data.append({"text": prompt})
        
        # Create dataset
        dataset = Dataset.from_list(formatted_data)
        
        # Tokenize dataset
        def tokenize_function(examples):
            return tokenizer(examples["text"], padding="max_length", truncation=True)
        
        tokenized_dataset = dataset.map(tokenize_function, batched=True)
        
        # Set up training arguments
        training_args = TrainingArguments(
            output_dir=self.output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            learning_rate=learning_rate,
            save_steps=500,
            save_total_limit=2,
        )
        
        # Create data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer, mlm=False
        )
        
        # Initialize trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
        )
        
        # Start training
        trainer.train()
        
        # Save the model
        model.save_pretrained(os.path.join(self.output_dir, "final"))
        tokenizer.save_pretrained(os.path.join(self.output_dir, "final"))
        
        return os.path.join(self.output_dir, "final")


@celery_app.task(bind=True)
def train_model_from_feedback(self, episode_ids):
    """Task to train a model based on judge feedback."""
    trainer = ModelTrainer()
    training_data = trainer.prepare_training_data(episode_ids)
    output_dir = trainer.fine_tune(training_data)
    
    # Update the model path in settings
    # This would require a mechanism to update settings at runtime
    # or store the path in a database for future reference
    
    return {
        "model_path": output_dir,
        "num_examples": len(training_data),
        "status": "success"
    } 