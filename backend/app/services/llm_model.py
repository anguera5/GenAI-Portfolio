import re
from fastapi import HTTPException
from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from app.core.config import get_settings
from app.core.prompts import (
    generate_code_template,
    generate_test_template,
    generate_documentation_template,
    generate_code_review_template,
)
from app.services.rag_model import build_langgraph, rag_answer_process
from app.services.chembl_sql_pipeline import ChemblSqlPipeline
import logging
import threading

_settings = get_settings()
logger = logging.getLogger(__name__)

class LLMModel:
    def __init__(self):
        self.model = _settings.openai_model
        self.temperature = _settings.temperature
        self.api_key = None
        self.llm = None
        self.embeddings = None
        self.vector_store_website = None
        self.vector_store_sql = None
        self.rag_chain = None
        self.chembl_pipeline = None
        # Simple in-memory session map for ChEMBL edit mode
        self._chembl_sessions: dict[str, dict] = {}
        # Minimal concurrency safety for (re)initialization
        self._init_lock = threading.RLock()

    def check_model_running(self, api_key: str):
        # Normalize provided key
        incoming_key = (api_key or '').strip()
        current_key = (self.api_key or '').strip()

        with self._init_lock:
            # Early exit if we already have a client and the key hasn't changed
            if self.llm and incoming_key == current_key:
                return True

            # Re-initialize only when a new, non-empty key differs from the current one
            if incoming_key and incoming_key != current_key:
                # Create a temporary client to validate the key before committing
                temp_llm = ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    openai_api_key=incoming_key,
                    reasoning_effort="minimal",
                )
                try:
                    # Tiny no-op call to validate the key; minimal cost
                    _ = temp_llm.invoke("ping")
                except Exception as ex:
                    logger.warning("API key validation failed: %s", ex)
                    # Do not change current client on failure
                    raise HTTPException(status_code=401, detail="Invalid API key or upstream not reachable.") from ex

                # Commit the new key and initialize the rest only after validation succeeds
                self.api_key = incoming_key
                self.llm = temp_llm
                self.embeddings = OpenAIEmbeddings(model=_settings.openai_embedding_model, api_key=incoming_key)
                self.vector_store_website = Chroma(
                    embedding_function=self.embeddings,
                    persist_directory="app/chroma_db",
                )
                self.vector_store_sql = Chroma(
                    collection_name="chembl_schema",
                    embedding_function=self.embeddings,
                    persist_directory="app/chroma_db",
                )

            # If model not yet initialized and no valid key provided now, error
            if not self.llm:
                raise HTTPException(status_code=400, detail="API key is required to initialize the model.")
            return True


    # ---------------------- Code Generation ----------------------
    def generate_code(self, prompt: str, language: str, api_key: str):
        logger.info("[LLM][generate] lang=%s prompt.len=%d", language, len(prompt or ""))
        self.check_model_running(api_key)
        if not prompt or len(prompt) < 1 or len(prompt) > 8000:
            raise HTTPException(status_code=400, detail="Please introduce code-related prompt")
        processed_prompt = generate_code_template(language, prompt)
        response = self.llm.invoke(processed_prompt)
        text = response.content or ""
        return self.strip_markdown_fences(text)

    # ---------------------- Tests Generation ----------------------
    def generate_tests(self, code: str):
        logger.info("[LLM][tests] code.len=%d", len(code or ""))
        if not self.llm:
            raise HTTPException(status_code=400, detail="Model not initialized; generate code first or supply API key.")
        processed_prompt = generate_test_template(code)
        response = self.llm.invoke(processed_prompt)
        text = response.content or ""
        return self.strip_markdown_fences(text)

    # ---------------------- Documentation Generation ----------------------
    def generate_docs(self, code: str):
        logger.info("[LLM][docs] code.len=%d", len(code or ""))
        if not self.llm:
            raise HTTPException(status_code=400, detail="Model not initialized; generate code first or supply API key.")
        processed_prompt = generate_documentation_template(code)
        response = self.llm.invoke(processed_prompt)
        text = response.content or ""
        return self.strip_markdown_fences(text)

    # ---------------------- Code Review Generation ----------------------
    def generate_code_review(self, title: str, body: str | None, diff_summary: str | None):
        logger.info("[LLM][code-review] title.len=%d body.len=%d", len(title or ""), len(body or ""))
        if not self.llm:
            raise HTTPException(status_code=400, detail="Model not initialized; supply API key via /generate first.")
        processed_prompt = generate_code_review_template(title, body or "", diff_summary or "")
        response = self.llm.invoke(processed_prompt)
        text = response.content or ""
        return self.strip_markdown_fences(text)
    
    def generate_rag_response(self, prompt, api_key, config_key):
        if not self.check_model_running(api_key) or not self.rag_chain:
            logger.info("Initializing RAG chain")
            logger.info("Using model: %s", self.llm.get_name())
            self.initialize_chain()
        return rag_answer_process(self.rag_chain, prompt, config_key)

    def initialize_chain(self):
        self.rag_chain = build_langgraph(self.llm, self.vector_store_website)
        return

    def run_chembl_full(self, prompt: str, limit: int, api_key: str):
        self.check_model_running(api_key)
        if not self.chembl_pipeline:
            self.chembl_pipeline = ChemblSqlPipeline(self.llm, self.vector_store_sql)
        return self.chembl_pipeline.run_all(prompt, limit)

    def chembl_session_set(self, memory_id: str, state: dict):
        # Store last state for a session id
        self._chembl_sessions[memory_id] = state

    def chembl_session_get(self, memory_id: str) -> dict | None:
        return self._chembl_sessions.get(memory_id)

    def chembl_apply_edit(self, memory_id: str, instruction: str, api_key: str, prev_sql: str | None = None) -> dict:
        """Apply a user tweak to the last SQL by asking the model to modify it based on the instruction.
        Returns a fresh state-like dict with updated sql, tables, and execution results.
        """
        self.check_model_running(api_key)
        prev = self.chembl_session_get(memory_id)
        if not prev:
            raise HTTPException(status_code=400, detail="Unknown memory_id; run a query first.")
        original_prompt = str(prev.get("prompt") or "")
        last_sql = str(prev.get("sql") or "")
        # Prefer caller-provided SQL if present to avoid relying solely on memory
        if prev_sql and prev_sql.strip():
            last_sql = prev_sql
        if not last_sql:
            raise HTTPException(status_code=400, detail="No SQL present for this session.")
        # Ensure pipeline exists and run the edit entry point (retrieve -> process -> synthesize -> execute -> repair)
        if not self.chembl_pipeline:
            self.chembl_pipeline = ChemblSqlPipeline(self.llm, self.vector_store_sql)
        try:
            state = self.chembl_pipeline.run_edit(prev_sql=last_sql, instruction=instruction, original_prompt=original_prompt, limit=100)
        except Exception as ex:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Edit pipeline error: {ex}") from ex
        # Persist updated session state
        self.chembl_session_set(memory_id, state)
        return state

    def chembl_reexecute(self, memory_id: str, limit: int, api_key: str) -> tuple[list[str], list[list]]:
        """Re-execute the last SQL for a session with a new LIMIT and persist rows/columns back to session."""
        self.check_model_running(api_key)
        prev = self.chembl_session_get(memory_id)
        if not prev:
            raise HTTPException(status_code=400, detail="Unknown memory_id; run a query first.")
        sql = str(prev.get("sql") or "")
        if not sql:
            raise HTTPException(status_code=400, detail="No SQL present for this session.")
        if not self.chembl_pipeline:
            self.chembl_pipeline = ChemblSqlPipeline(self.llm, self.vector_store_sql)
        cols, rows = self.chembl_pipeline.execute_only(sql, limit or 100)
        prev["columns"], prev["rows"] = cols, rows
        self.chembl_session_set(memory_id, prev)
        return cols, rows

    # ---------------------- Helpers ----------------------
    def strip_markdown_fences(self, text: str) -> str:
        """Remove triple backtick code fences with optional language hints."""
        if not text:
            return text
        pattern = r"^\s*```[a-zA-Z0-9_\-]*\s*\n([\s\S]*?)\n\s*```\s*$"
        m = re.match(pattern, text.strip())
        if m:
            return m.group(1).strip()
        return text.strip()
