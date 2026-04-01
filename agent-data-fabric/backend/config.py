"""Application configuration from environment variables."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM — Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_deployment: str = "gpt-4o"
    api_version: str = "2024-05-01-preview"

    # LLM — Ollama fallback
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5436
    postgres_db: str = "agent_data_fabric"
    postgres_user: str = "adf_user"
    postgres_password: str = "adf_secret_password_change_me"

    # Encryption
    fernet_key: str = ""

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Ports
    backend_port: int = 7790
    frontend_port: int = 7791
    mcp_server_port: int = 7792
    mcp_inspector_port: int = 6274

    # URLs
    mcp_server_url: str = "http://localhost:7792/sse"
    backend_url: str = "http://localhost:7790"

    # App
    app_name: str = "Agentic Data Fabric"
    debug: bool = False
    log_level: str = "INFO"

    # Docker
    docker_host: str = "unix:///var/run/docker.sock"
    mcp_filesystem_path: str = "/tmp/adf-files"

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    azure_storage_account_key: str = ""
    azure_storage_container_name: str = ""

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def database_url_sync(self) -> str:
        return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def use_azure_openai(self) -> bool:
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
