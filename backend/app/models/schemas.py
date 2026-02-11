from pydantic import BaseModel, Field
from typing import Any

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=0, max_length=8000)
    language: str
    api_key: str


class GenerateResponse(BaseModel):
    code: str
    language: str


class BasicRequest(BaseModel):
    code: str = Field(..., min_length=1)


class BasicResponse(BaseModel):
    code: str = Field(..., min_length=1)


class ErrorResponse(BaseModel):
    detail: str


class PullRequestInfo(BaseModel):
    title: str
    body: str | None = None
    base_branch: str | None = None
    head_branch: str | None = None
    repository: str | None = None
    diff_url: str | None = None


class CodeReviewResponse(BaseModel):
    review: str

class CodeReviewByUrlRequest(BaseModel):
    url: str

class FpfRagRequest(BaseModel):
    prompt: str = Field(..., min_length=0, max_length=8000)
    api_key: str
    config_key: str
class FpfRagResponse(BaseModel):
    reply: str

class ChemblSqlPlanRequest(BaseModel):
    prompt: str
    api_key: str
    memory_id: str | None = None


class ChemblSqlPlanResponse(BaseModel):
    sql: str
    # Allow backend to return structured dictionaries for tables
    related_tables: list[Any] | None = None


class ChemblSqlExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    limit: int | None = Field(default=100, ge=1)


class ChemblSqlExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list]


class ChemblSqlEditRequest(BaseModel):
    memory_id: str = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1)
    api_key: str
    # Optional: current SQL from the client to avoid relying solely on server session state
    prev_sql: str | None = None

class ChemblSqlEditResponse(BaseModel):
    sql: str
    related_tables: list[Any] | None = None
    columns: list[str]
    rows: list[list]
    retries: int
    repaired: bool
    no_context: bool
    not_chembl: bool
    chembl_reason: str | None = None
    optimized_guidelines: str | None = None


class ChemblSqlReexecuteRequest(BaseModel):
    memory_id: str = Field(..., min_length=1)
    limit: int = Field(default=100, ge=1)
    api_key: str

class ChemblSqlReexecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list]

