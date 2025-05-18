from pydantic import BaseSettings, Field
from typing import Literal


class Settings(BaseSettings):
    # OpenAI / LLM
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", env="OPENAI_MODEL")
    embed_model: str = Field("text-embedding-3-small", env="EMBED_MODEL")

    # Vector store
    vector_backend: Literal["pg", "infinity"] = Field("pg", env="VECTOR_BACKEND")
    vector_dim: int = Field(1536, env="VECTOR_DIM")
    vector_host: str = Field("infinity", env="VECTOR_HOST")
    vector_port: int = Field(8000, env="VECTOR_PORT")

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