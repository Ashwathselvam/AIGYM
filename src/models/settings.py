from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM Configuration
    llm_model_name: str = Field("microsoft/phi-2", env="LLM_MODEL_NAME")  # or mistralai/Mistral-7B-v0.1
    embed_model_name: str = Field("sentence-transformers/all-MiniLM-L6-v2", env="EMBED_MODEL_NAME")
    use_gpu: bool = Field(False, env="USE_GPU")  # Set to True to use GPU, False for CPU
    
    # OpenAI Configuration
    openai_api_key: str = Field("", env="OPENAI_API_KEY")  # Empty default, making it optional
    
    # Training Configuration
    models_dir: str = Field("./trained_models", env="MODELS_DIR")
    
    # Vector store
    vector_backend: Literal["pg", "qdrant"] = Field("pg", env="VECTOR_BACKEND")
    vector_dim: int = Field(384, env="VECTOR_DIM")  # Default for sentence-transformers model
    vector_host: str = Field("qdrant", env="VECTOR_HOST")
    vector_port: int = Field(6333, env="VECTOR_PORT")

    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # NebulaGraph
    nebula_host: str = Field("nebula-graphd", env="NEBULA_HOST")
    nebula_port: int = Field(9669, env="NEBULA_PORT")
    nebula_user: str = Field("root", env="NEBULA_USER")
    nebula_pass: str = Field("password", env="NEBULA_PASS")

    # Redis / Celery
    redis_url: str = Field("redis://redis:6379/0", env="REDIS_URL")

    class Config:
        case_sensitive = False
        env_file = ".env"


settings = Settings() 