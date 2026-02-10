import os
from pydantic import BaseModel


class Settings(BaseModel):
    openai_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-large"
    temperature: str
    app_name: str = "CodeGen API"


def get_settings() -> Settings:
    return Settings(
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        temperature=os.getenv("TEMPERATURE", "0.3"),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
    )
