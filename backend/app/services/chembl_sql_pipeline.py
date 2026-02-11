from __future__ import annotations

import os
import json
import re
import time
import sqlite3
from typing import Any, List, Tuple, TypedDict
import uuid

from langgraph.graph import StateGraph, END
import logging


DB_PATH = os.getenv("CHEMBL_SQLITE_PATH", "app/chembl/chembl_36.db")
READ_ONLY_URI = f"file:{DB_PATH}?mode=ro"

FORBIDDEN_TOKENS = (
    ";",  # prevent multiple statements
    "pragma",
    "attach",
    "detach",
    "vacuum",
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "begin",
    "commit",
    "rollback",
)


class SqlState(TypedDict, total=False):
    prompt: str
    enhanced_query: str
    # Previous SQL when coming from edit workflow
    prev_sql: str
    # Original question prompt when editing (optional)
    original_prompt: str
    related_texts: List[str]
    structured_tables: List[dict]
    sql: str
    limit: int
    retries: int
    columns: List[str]
    rows: List[List[Any]]
    error: str
    no_context: bool
    not_chembl: bool
    chembl_reason: str
    # Repair/resynthesis control
    repaired: bool
    exec_failed: bool
    attempts: List[dict]
    optimized_guidelines: str
    loops: int


class ChemblSqlPipeline:
    """End-to-end ChEMBL SQL pipeline (plan → retrieve → synthesize → execute) using LangGraph."""

    def __init__(self, llm, vector_store_sql):
        self.llm = llm
        self.vector_store = vector_store_sql
    # Graph is constructed per run to avoid any internal runner state leaks.
    # See run_all for per-call build.

    # ----------------- Utilities (logging) -----------------
    def _preview(self, text: str, max_len: int = 140) -> str:
        t = (text or "").strip().replace("\n", " ⏎ ")
        return (t[: max_len - 1] + "…") if len(t) > max_len else t

    def _log_step(self, step: str, **fields: Any) -> None:
        parts = [f"{k}={v}" for k, v in fields.items() if v is not None]
        message = " | ".join(parts)
        logging.getLogger(__name__).info("[CHEMBL][pipe][%s] %s", step, message)

    # ----------------- Public API -----------------
    def plan_and_synthesize(self, prompt: str) -> Tuple[str, List[dict]]:
        t0 = time.perf_counter()
        self._log_step("START", prompt_preview=self._preview(prompt), limit="n/a")
        enhanced = self._plan_query(prompt)
        self._log_step("PLAN.done", len=len(enhanced), preview=self._preview(enhanced))
        related_texts = self._retrieve_related_texts(enhanced, k=5)
        names_preview = self._extract_table_names_preview(related_texts)
        self._log_step("RETRIEVE.done", docs=len(related_texts), tables=names_preview)
        structured = [self._to_structured_table_dict(t) for t in related_texts]
        sql = self._synthesize_sql(enhanced, related_texts)
        self._log_step("SYNTH.done", sql_len=len(sql), sql_head=self._preview(sql, 100))
        self._log_step("END", took_ms=int((time.perf_counter() - t0) * 1000))
        return sql, structured

    def execute_only(self, sql: str, limit: int | None = 100) -> Tuple[List[str], List[List[Any]]]:
        return self._execute_sql(sql, limit or 100)

    def run_all(self, prompt: str, limit: int | None = 100) -> SqlState:
        """Run the full graph and return final state with sql, structured tables, and results.

        - Builds a fresh graph per run (robust after exceptions, thread-safe by isolation).
        - Optional soft timeout (CHEMBL_PIPELINE_TIMEOUT_S). Set to 0 to disable.
        """
        run_id = uuid.uuid4().hex[:8]
        inputs: SqlState = {
            "prompt": prompt,
            "limit": int(limit or 100),
            "retries": 0,
            "attempts": [],
            "loops": 0,
        }
        self._log_step("START", run_id=run_id, prompt_preview=self._preview(prompt), limit=inputs["limit"])
        t0 = time.perf_counter()
        # Read soft timeout from env (seconds); default 0 = disabled
        try:
            _budget = float(os.getenv("CHEMBL_PIPELINE_TIMEOUT_S", "0"))
        except (TypeError, ValueError):
            _budget = 0.0
        last: SqlState | None = None
        graph = self._build_graph(entry="classify")  # per-run
        for step in graph.stream(inputs, stream_mode="values"):
            last = step
            if _budget and _budget > 0 and (time.perf_counter() - t0) > _budget:
                # Leave a clear message; frontend will show it in the snackbar
                raise ValueError(f"Pipeline timeout: exceeded {_budget:.0f}s. Please try again or refine your prompt.")
        self._log_step(
            "END",
            run_id=run_id,
            sql_len=len((last or {}).get("sql", "")),
            rows=len((last or {}).get("rows", [])),
            cols=len((last or {}).get("columns", [])),
            took_ms=int((time.perf_counter() - t0) * 1000),
        )
        return last or {}

    # ----------------- LangGraph -----------------
    def _build_graph(self, entry: str = "classify"):
        g = StateGraph(SqlState)

        def node_classify(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            is_chembl, reason, conf = self._classify_chembl_relevance(state.get("prompt") or "")
            self._log_step(
                "CLASSIFY.done",
                is_chembl=is_chembl,
                confidence=f"{conf:.2f}",
                took_ms=int((time.perf_counter() - t0) * 1000),
                reason_preview=self._preview(reason or "", 160),
            )
            if not is_chembl:
                return {
                    "not_chembl": True,
                    "no_context": True,
                    "chembl_reason": reason or "Query not related to ChEMBL domain.",
                    "related_texts": [],
                    "structured_tables": [],
                    "sql": "",
                    "columns": [],
                    "rows": [],
                }
            return {"not_chembl": False, "chembl_reason": reason or ""}

        def node_plan(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            if state.get("not_chembl"):
                self._log_step("PLAN.skip", reason="not_chembl")
                return {}
            enhanced = self._plan_query(state.get("prompt") or "")
            self._log_step("PLAN.done", len=len(enhanced), took_ms=int((time.perf_counter() - t0) * 1000))
            return {"enhanced_query": enhanced}

        def node_retrieve(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            if state.get("not_chembl"):
                self._log_step("RETRIEVE.skip", reason="not_chembl")
                return {"related_texts": [], "structured_tables": [], "no_context": True}
            eq = state.get("enhanced_query") or ""
            related_texts = self._retrieve_related_texts(eq, k=5)
            names_preview = self._extract_table_names_preview(related_texts)
            self._log_step("RETRIEVE.done", docs=len(related_texts), tables=names_preview, took_ms=int((time.perf_counter() - t0) * 1000))
            structured = [self._to_structured_table_dict(t) for t in related_texts]
            return {"related_texts": related_texts, "structured_tables": structured, "no_context": len(related_texts) == 0}

        def node_process(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            if state.get("not_chembl"):
                self._log_step("PROCESS.skip", reason="not_chembl")
                return {}
            if not state.get("related_texts"):
                self._log_step("PROCESS.skip", reason="no_related_docs")
                return {"optimized_guidelines": ""}
            try:
                base_prompt = (state.get("original_prompt") or state.get("prompt") or "")
                guidelines = self._build_optimized_guidelines(base_prompt, state.get("related_texts") or [])
            except ValueError as e:
                self._log_step("PROCESS.error", error=str(e))
                guidelines = (
                    "- Use exact column names and proper JOINs on keys (PK/FK).\n"
                    "- Filter early with WHERE; aggregate only when needed.\n"
                    "- Return concise columns; avoid SELECT *.\n"
                    "- Respect SQLite syntax."
                )
            self._log_step("PROCESS.done", took_ms=int((time.perf_counter() - t0) * 1000), preview=self._preview(guidelines, 160))
            return {"optimized_guidelines": guidelines}

        def node_synthesize(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            if state.get("not_chembl"):
                self._log_step("SYNTH.skip", reason="not_chembl")
                return {"sql": "", "no_context": True}
            if not state.get("related_texts"):
                self._log_step("SYNTH.skip", reason="no_context")
                return {"sql": "", "no_context": True}
            sql = self._synthesize_sql(
                state.get("enhanced_query") or "",
                state.get("related_texts") or [],
                state.get("attempts") or [],
                state.get("optimized_guidelines") or "",
                edit_mode=bool(state.get("prev_sql")),
            )
            # Edit-guard: if in edit mode and the new SQL drops previous tables, retry once with stricter guidance
            prev_sql_ctx = (state.get("prev_sql") or "").strip()
            if prev_sql_ctx:
                prev_tables = self._extract_tables_from_sql(prev_sql_ctx)
                new_tables = self._extract_tables_from_sql(sql)
                try:
                    self._log_step(
                        "SYNTH.tables",
                        prev=",".join(sorted(prev_tables)) or "(none)",
                        new=",".join(sorted(new_tables)) or "(none)",
                    )
                except Exception:
                    pass
                # Allow rewrite only if instruction clearly asks for major changes
                instr = (state.get("prompt") or "").lower()
                rewrite_markers = [
                    "rewrite", "different table", "change table", "use table", "switch",
                    "replace", "new query", "start over", "new tables", "totally different"
                ]
                allow_rewrite = any(m in instr for m in rewrite_markers)
                if prev_tables and new_tables and not prev_tables.issubset(new_tables) and not allow_rewrite:
                    guard_msg = (
                        "STRICT EDIT GUARD: Reuse exactly these FROM/JOIN tables from the current SQL: "
                        + ", ".join(sorted(prev_tables))
                        + ". Do not remove or replace them. Only adjust filters, projections, or aliases as needed."
                    )
                    guidelines = (state.get("optimized_guidelines") or "").strip()
                    if guidelines:
                        guidelines = guidelines + "\n" + guard_msg
                    else:
                        guidelines = guard_msg
                    try:
                        sql2 = self._synthesize_sql(
                            state.get("enhanced_query") or "",
                            state.get("related_texts") or [],
                            state.get("attempts") or [],
                            guidelines,
                            edit_mode=True,
                        )
                        new_tables2 = self._extract_tables_from_sql(sql2)
                        if prev_tables.issubset(new_tables2):
                            self._log_step("SYNTH.retry_guard.success")
                            sql = sql2
                        else:
                            self._log_step(
                                "SYNTH.retry_guard.nochange",
                                prev=",".join(sorted(prev_tables)) or "(none)",
                                new=",".join(sorted(new_tables2)) or "(none)",
                            )
                    except Exception as e:
                        # If retry fails, keep original sql and proceed to execution/repair
                        self._log_step("SYNTH.retry_guard.error", error=str(e))
            self._log_step("SYNTH.done", sql_len=len(sql), sql_head=self._preview(sql, 100), took_ms=int((time.perf_counter() - t0) * 1000))
            return {"sql": sql, "exec_failed": False}

        def node_execute(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            sql = state.get("sql") or ""
            limit = state.get("limit") or 100
            retries = int(state.get("retries") or 0)
            attempts = list(state.get("attempts") or [])
            if state.get("no_context"):
                self._log_step("EXEC.skip", reason="no_context")
                return {"columns": [], "rows": [], "error": "", "retries": retries, "no_context": True, "exec_failed": False}
            try:
                cols, rows = self._execute_sql(sql, limit)
                self._log_step("EXEC.done", rows=len(rows), cols=len(cols), took_ms=int((time.perf_counter() - t0) * 1000))
                return {"columns": cols, "rows": rows, "error": "", "retries": retries, "exec_failed": False}
            except ValueError as e:
                err = str(e)
                self._log_step("EXEC.fail", retries=retries, error_preview=self._preview(err, 160))
                attempts.append({"stage": "execute", "sql": sql, "error": err})
                return {"columns": [], "rows": [], "error": err, "retries": retries, "exec_failed": True, "attempts": attempts}

        def node_repair(state: SqlState) -> SqlState:
            t0 = time.perf_counter()
            if state.get("no_context") or not state.get("exec_failed"):
                self._log_step("REPAIR.skip", reason=("no_context" if state.get("no_context") else "no_exec_fail"))
                return {}
            retries = int(state.get("retries") or 0)
            loops = int(state.get("loops") or 0)
            attempts = list(state.get("attempts") or [])
            prev_sql = state.get("sql") or ""
            last_err = state.get("error") or ""
            repaired_sql = self._repair_sql(
                state.get("prompt") or "",
                prev_sql,
                last_err,
                state.get("related_texts") or [],
            )
            self._log_step("REPAIR.sql", head=self._preview(repaired_sql, 160), took_ms=int((time.perf_counter() - t0) * 1000))
            try:
                cols2, rows2 = self._execute_sql(repaired_sql, state.get("limit") or 100)
                self._log_step("REPAIR.done", rows=len(rows2), cols=len(cols2))
                attempts.append({"stage": "repair", "sql": repaired_sql, "error": ""})
                return {
                    "sql": repaired_sql,
                    "columns": cols2,
                    "rows": rows2,
                    "error": "",
                    "retries": retries + 1,
                    "repaired": True,
                    "exec_failed": False,
                    "attempts": attempts,
                }
            except ValueError as e2:
                err2 = str(e2)
                self._log_step("REPAIR.fail", error_preview=self._preview(err2, 160))
                attempts.append({"stage": "repair", "sql": repaired_sql, "error": err2})
                return {
                    "sql": repaired_sql,
                    "columns": [],
                    "rows": [],
                    "error": err2,
                    "retries": retries + 1,
                    "loops": loops + 1,
                    "repaired": False,
                    "exec_failed": True,
                    "attempts": attempts,
                }

        # New: edit entry node
        def node_edit_entry(state: SqlState) -> SqlState:
            """
            Compose an enhanced query from the original prompt, the user's edit instruction (provided in state.prompt),
            and the previous SQL (state.prev_sql). This feeds retrieval directly, skipping classify/plan for edits.
            """
            instr = (state.get("prompt") or "").strip()
            prev = (state.get("prev_sql") or "").strip()
            # Optionally include original question if provided separately in state under 'original_prompt'
            original_prompt = (state.get("original_prompt") or "").strip()
            self._log_step("EDIT.entry", instr_len=len(instr), prev_len=len(prev), has_orig=bool(original_prompt))
            parts = []
            if original_prompt:
                parts.append("Original question:\n" + original_prompt)
            parts.append("Edit instruction:\n" + (instr or "(none)"))
            if prev:
                parts.append("Current SQL (context):\n" + prev)
            parts.append("Goal: apply a minimal change; preserve existing tables, joins, and CTEs unless explicitly requested.")
            enhanced = "\n\n".join(parts)
            return {
                "enhanced_query": enhanced,
                # make sure downstream nodes don't early-exit at this point
                "not_chembl": False,
                "no_context": False,
            }

        # Wire graph
        g.add_node("classify", node_classify)
        g.add_node("plan", node_plan)
        g.add_node("retrieve", node_retrieve)
        g.add_node("process", node_process)
        g.add_node("synthesize", node_synthesize)
        g.add_node("execute", node_execute)
        g.add_node("repair", node_repair)
        g.add_node("edit_entry", node_edit_entry)

        if entry == "classify":
            g.set_entry_point("classify")
            g.add_conditional_edges(
                "classify",
                lambda s: "end" if s.get("not_chembl") else "plan",
                {"plan": "plan", "end": END},
            )
            g.add_edge("plan", "retrieve")
        elif entry == "edit":
            g.set_entry_point("edit_entry")
            g.add_edge("edit_entry", "retrieve")
        else:
            # default to classify path if unknown
            g.set_entry_point("classify")
            g.add_edge("plan", "retrieve")
        g.add_edge("retrieve", "process")
        g.add_edge("process", "synthesize")
        g.add_edge("synthesize", "execute")
        g.add_conditional_edges(
            "execute",
            lambda s: "end" if (not s.get("exec_failed")) or s.get("no_context") else "repair",
            {"repair": "repair", "end": END},
        )
        def _after_repair(s: SqlState) -> str:
            if not s.get("exec_failed"):
                return "end"
            loops = int(s.get("loops") or 0)
            # Exit if loops >= 3, else go back to process
            return "process" if loops < 3 else "end"
        g.add_conditional_edges("repair", _after_repair, {"process": "process", "end": END})

        return g.compile()

    def run_edit(self, prev_sql: str, instruction: str, original_prompt: str | None = None, limit: int | None = 100) -> SqlState:
        """
        Edit entry-point: start the graph at 'edit_entry' so we skip classify/plan.
        The enhanced query includes original prompt (if available), the edit instruction, and the current SQL.
        Flow: edit_entry -> retrieve -> process -> synthesize -> execute -> (conditional) repair.
        """
        run_id = uuid.uuid4().hex[:8]
        inputs: SqlState = {
            "prompt": instruction or "",
            "original_prompt": (original_prompt or ""),  # carried for logging/guidelines context
            "prev_sql": prev_sql or "",
            "limit": int(limit or 100),
            "retries": 0,
            "attempts": [],
            "loops": 0,
            "not_chembl": False,
            "no_context": False,
        }
        self._log_step(
            "START.EDIT",
            run_id=run_id,
            instr_preview=self._preview(instruction or ""),
            prev_head=self._preview(prev_sql or "", 120),
            limit=inputs["limit"],
        )
        t0 = time.perf_counter()
        try:
            _budget = float(os.getenv("CHEMBL_PIPELINE_TIMEOUT_S", "0"))
        except (TypeError, ValueError):
            _budget = 0.0
        last: SqlState | None = None
        graph = self._build_graph(entry="edit")
        for step in graph.stream(inputs, stream_mode="values"):
            last = step
            # Respect optional soft timeout only if configured
            if _budget and _budget > 0 and (time.perf_counter() - t0) > _budget:
                raise ValueError(f"Pipeline timeout: exceeded {_budget:.0f}s. Please try again or refine your prompt.")
        self._log_step(
            "END.EDIT",
            run_id=run_id,
            sql_len=len((last or {}).get("sql", "")),
            rows=len((last or {}).get("rows", [])),
            cols=len((last or {}).get("columns", [])),
            took_ms=int((time.perf_counter() - t0) * 1000),
        )
        return last or {}

    # ----------------- Steps (logic) -----------------
    def _plan_query(self, prompt: str) -> str:
        system = (
            "You are a SQL expert planner for the ChEMBL database.\n\n"
            "=== PLANNING PROCESS ===\n\n"
            "STEP 1: EXTRACT KEY REQUIREMENTS\n"
            "- What specific data is the user asking for?\n"
            "- What entities are involved (molecules, targets, assays, activities)?\n"
            "- What conditions or filters are specified?\n\n"
            "STEP 2: IDENTIFY DATA NEEDS\n"
            "- Which ChEMBL tables likely contain this data?\n"
            "- What relationships between tables are needed?\n"
            "- What key columns are essential?\n\n"
            "OUTPUT: Provide a clear, detailed analysis in 2-4 sentences covering these aspects."
        )
        msg = [("system", system), ("user", prompt)]
        self._log_step("PLAN.start", prompt_len=len(prompt))
        try:
            out = self.llm.invoke(msg)
        except Exception as e:  # noqa: BLE001 - upstream API may raise various exceptions
            raise ValueError(f"Planner LLM error: {e}") from e
        return (getattr(out, "content", "") or "").strip()

    def _retrieve_related_texts(self, query: str, k: int = 5) -> List[str]:
        self._log_step("RETRIEVE.start", query_preview=self._preview(query), k=k)
        docs = self.vector_store.similarity_search(query, k=k)
        seen: List[str] = []
        for d in docs:
            t = (d.metadata or {}).get("text") or getattr(d, "page_content", None)
            if t and t not in seen:
                seen.append(t)
        return seen

    def _synthesize_sql(self, prompt: str, related_tables: List[str], attempts: List[dict] | None = None, guidelines: str | None = None, edit_mode: bool = False) -> str:
        context = "\n\n".join(f"- {t}" for t in related_tables) if related_tables else "(none)"
        prev_attempts_txt = ""
        if attempts:
            try:
                # Keep only last 2 attempts for brevity
                last = attempts[-2:]
                lines = []
                for i, a in enumerate(last, 1):
                    sql_prev = str(a.get("sql") or "").strip()
                    err_prev = str(a.get("error") or "").strip()
                    if sql_prev:
                        lines.append(f"Attempt {i} SQL:\n{sql_prev}")
                    if err_prev:
                        lines.append(f"Attempt {i} error:\n{err_prev}")
                if lines:
                    prev_attempts_txt = "\n\nPrevious attempts and errors (for correction):\n" + "\n\n".join(lines)
            except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                prev_attempts_txt = ""
        guide_txt = ("\n\nOptimization guidelines to follow:\n" + (guidelines or "").strip()) if (guidelines and guidelines.strip()) else ""
        user = (
            "User question:\n" + prompt + "\n\n" +
            "Related tables (retrieved):\n" + context +
            prev_attempts_txt + guide_txt + "\n\n" +
            "Write a single valid and optimized SQLite SQL query that best answers the question using these tables."
        )
        system = (
            "You are a helpful assistant that implements robust and optimized SQLite SQL queries for the ChEMBL database.\n\n"
            "=== PROCESS - FOLLOW THESE STEPS IN ORDER ===\n\n"
            "STEP 1: UNDERSTAND THE QUESTION\n"
            "- Read the user question carefully\n"
            "- Identify what data is being requested\n"
            "- Note any filters, aggregations, or specific conditions\n\n"
            "STEP 2: ANALYZE THE SCHEMA\n"
            "- Review the related tables provided\n"
            "- Identify which tables contain the needed data\n"
            "- Map out the join relationships (PK/FK connections)\n"
            "- Verify exact column names in each table\n\n"
            "STEP 3: CONSTRUCT THE QUERY\n"
            "- Write SELECT with specific columns (avoid SELECT *)\n"
            "- Add FROM clause with primary table\n"
            "- Add JOIN clauses with explicit ON conditions\n"
            "- Add WHERE clause for filters based on what the user asked, do not add extra unnecessary conditions unless requested\n"
            "- Add GROUP BY and aggregate functions if needed\n"
            "- Do not include LIMIT clauses\n"
            "- Verify all columns and tables match the schema exactly\n\n"
            "=== OUTPUT REQUIREMENTS ===\n"
            "- Output ONLY the final SQL query - no explanations, no markdown, no steps shown\n"
            "- If related tables are '(none)', output exactly: Sorry, I am unable to answer this.\n"
            "- Use ONLY table and column names from the related tables provided\n\n"
        )
        if edit_mode:
            system += (
                "\n- EDIT MODE: If a 'Current SQL (context)' is provided, minimally modify that SQL to satisfy the edit instruction."
                "\n  Preserve its overall structure: CTEs, FROM/JOIN tables, join conditions, and selected columns."
                "\n  Only add or adjust filters/aliases/projections as needed by the instruction; do not rewrite from scratch."
            )
        self._log_step("SYNTH.start", prompt_len=len(prompt), tables=len(related_tables))
        try:
            out = self.llm.invoke([("system", system), ("user", user)])
        except Exception as e:  # noqa: BLE001 - upstream API may raise various exceptions
            raise ValueError(f"Synthesis LLM error: {e}") from e
        sql = (getattr(out, "content", "") or "").strip()
        # Remove markdown code fences if present
        if sql.startswith("````") or sql.startswith("```"):
            sql = sql.strip('`')
            if sql.lower().startswith("sql"):
                sql = sql[3:]
            sql = sql.strip()
            if sql.endswith("````"):
                sql = sql[:-4].strip()
            elif sql.endswith("```"):
                sql = sql[:-3].strip()
            self._log_step("SYNTH.unfence", sql_head=self._preview(sql, 100))
        return sql

    def _build_optimized_guidelines(self, prompt: str, related_texts: List[str]) -> str:
        """Generate concise, actionable SQL optimization guidelines based on retrieved schema snippets."""
        tables_summary = "\n\n".join(related_texts[:5])  # cap prompt size
        system = (
            "You are a senior data engineer. Draft precise guidelines to produce a high-quality, efficient SQLite query for the ChEMBL-like schema described.\n\n"
            "=== GUIDELINE GENERATION PROCESS ===\n\n"
            "STEP 1: SCHEMA ANALYSIS\n"
            "- Identify the tables mentioned in the schema excerpts\n"
            "- Note the primary keys (PK) and foreign keys (FK)\n"
            "- Understand how tables relate to each other\n\n"
            "STEP 2: QUERY STRATEGY\n"
            "- Determine which tables to join based on the user question\n"
            "- Identify specific join keys (e.g., molregno, assay_id)\n"
            "- Determine what filters to apply early (push-down optimization)\n\n"
            "STEP 3: OPTIMIZATION ADVICE\n"
            "- Suggest minimal column selection (avoid SELECT *)\n"
            "- Recommend proper filtering order\n"
            "- Note any aggregation or grouping needs\n\n"
            "=== OUTPUT FORMAT ===\n"
            "Provide exactly 4-8 concise bullet points with concrete advice.\n"
            "NO SQL code - only strategic guidance.\n\n"
            "Example guideline:\n"
            "- Join molecule_dictionary to activities on molregno (PK/FK)\n"
            "- Filter activities WHERE standard_type = 'IC50' early\n"
            "- Select only: chembl_id, pref_name, standard_value"
        )
        user = (
            "User question:\n" + (prompt or "").strip() + "\n\n" +
            "Relevant schema excerpts:\n" + tables_summary
        )
        self._log_step("PROCESS.guidelines.start")
        try:
            out = self.llm.invoke([("system", system), ("user", user)])
        except Exception as e:  # noqa: BLE001 - upstream API may raise various exceptions
            raise ValueError(f"Guidelines LLM error: {e}") from e
        text = (getattr(out, "content", "") or "").strip()
        # Strip potential code fences or prose wrappers
        if text.startswith("````") or text.startswith("```"):
            text = text.strip('`')
            text = text.strip()
            if text.endswith("````"):
                text = text[:-4].strip()
            elif text.endswith("```"):
                text = text[:-3].strip()
        return text

    def _classify_chembl_relevance(self, prompt: str) -> Tuple[bool, str, float]:
        """Decide if the prompt is related to the ChEMBL database domain.

        Returns (is_chembl, reason, confidence[0..1]).
        """
        description = (
            "ChEMBL is a large-scale bioactivity database focused on small molecules, targets (proteins), assays, and activities. "
            "It contains tables for molecules/compounds (identifiers, structures like SMILES/InChI), targets (e.g., CHEMBL IDs, UniProt links), assays, activities (IC50, EC50, Ki, potency, pChEMBL), mechanisms of action, indications, references/publications, and related metadata. "
            "Queries typically involve discovering relationships between compounds, targets, assays, activities, mechanisms, and properties (e.g., molecular weight)."
        )
        system = (
            "You are a strict classifier that determines whether a user question is about the ChEMBL bioactivity database domain.\n\n"
            "OUTPUT FORMAT - Respond with EXACTLY this JSON structure (no additional text):\n"
            "{\"is_chembl\": true, \"confidence\": 0.95, \"reason\": \"Question asks about...\"}\n\n"
            "Classification criteria:\n"
            "- Drug-like small molecules, compounds, chemical structures\n"
            "- Biological targets, proteins, UniProt IDs\n"
            "- Assays, bioactivity measurements (IC50, EC50, Ki, potency)\n"
            "- Mechanisms of action, drug indications\n"
            "- ChEMBL database schema or tables\n\n"
            "Set is_chembl=true if ANY of these apply, false otherwise."
        )
        user = (
            "ChEMBL description:\n" + description + "\n\n" +
            "User question:\n" + (prompt or "").strip()
        )
        try:
            out = self.llm.invoke([("system", system), ("user", user)])
        except Exception as e:  # noqa: BLE001 - upstream API may raise various exceptions
            self._log_step("CLASSIFY.error", error=str(e))
        else:
            text = (getattr(out, "content", "") or "").strip()
            data = None
            # Attempt robust JSON parse
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # Try to extract JSON object if surrounded by prose or code fences
                m = re.search(r"\{[\s\S]*\}", text)
                if m:
                    data = json.loads(m.group(0))
            if isinstance(data, dict):
                is_chembl = bool(data.get("is_chembl"))
                conf = float(data.get("confidence", 0))
                reason = str(data.get("reason") or "")
                return is_chembl, reason, max(0.0, min(1.0, conf))

        # Heuristic fallback
        p = (prompt or "").lower()
        keywords = [
            "chembl", "assay", "assays", "activity", "activities", "bioactivity", "ic50", "ec50", "ki", "potency", "pchembl",
            "compound", "compounds", "molecule", "molecules", "smiles", "inchi", "target", "targets", "uniprot",
            "mechanism", "indication", "binding", "affinity"
        ]
        score = sum(1 for k in keywords if k in p) / max(1, len(keywords))
        is_chembl = ("chembl" in p) or score >= 0.08
        reason = "Heuristic classification based on keyword overlap."
        return is_chembl, reason, min(1.0, max(0.0, score))

    def _repair_sql(self, original_prompt: str, prev_sql: str, error_message: str, related_tables: List[str]) -> str:
        """Ask the model to fix the previous SQL using the SQLite error as feedback."""
        context = "\n\n".join(f"- {t}" for t in related_tables) if related_tables else "(none)"
        system = (
            "You are a SQLite expert that fixes invalid queries for the ChEMBL database.\n\n"
            "=== REPAIR PROCESS - FOLLOW IN ORDER ===\n\n"
            "STEP 1: ANALYZE THE ERROR\n"
            "- Read the SQLite error message carefully\n"
            "- Identify the specific issue (column not found, table not found, syntax error, etc.)\n"
            "- Locate where in the SQL the error occurs\n\n"
            "STEP 2: CHECK THE SCHEMA\n"
            "- Review the related tables provided\n"
            "- Verify the correct table names\n"
            "- Verify the correct column names in each table\n"
            "- Check join relationships and keys\n\n"
            "STEP 3: FIX THE QUERY\n"
            "- Make MINIMAL changes - fix only what caused the error\n"
            "- Use exact table and column names from the schema\n"
            "- Ensure proper JOIN syntax with explicit ON clauses\n"
            "- Verify all referenced columns exist in their tables\n\n"
            "=== COMMON ERROR PATTERNS ===\n"
            "- 'no such column': Check exact column name spelling in schema\n"
            "- 'no such table': Use exact table name from related tables\n"
            "- 'syntax error': Check JOIN ON syntax, missing commas, quote matching\n"
            "- 'ambiguous column': Add table aliases (e.g., m.chembl_id)\n\n"
            "=== OUTPUT ===\n"
            "Output ONLY the corrected SQL query - no explanations, no markdown."
        )
        user = (
            "User question (for context):\n" + original_prompt + "\n\n"
            "Previous SQL (failed):\n" + prev_sql + "\n\n"
            "SQLite error message:\n" + error_message + "\n\n"
            "Related tables (retrieved):\n" + context + "\n\n"
            "Produce a corrected, valid SQLite SQL query that answers the user's question using the related tables."
        )
        self._log_step("REPAIR.start")
        try:
            out = self.llm.invoke([("system", system), ("user", user)])
        except Exception as e:  # noqa: BLE001 - upstream API may raise various exceptions
            raise ValueError(f"Repair LLM error: {e}") from e
        sql = (getattr(out, "content", "") or "").strip()
        if sql.startswith("````") or sql.startswith("```"):
            sql = sql.strip('`')
            if sql.lower().startswith("sql"):
                sql = sql[3:]
            sql = sql.strip()
            if sql.endswith("````"):
                sql = sql[:-4].strip()
            elif sql.endswith("```"):
                sql = sql[:-3].strip()
            self._log_step("REPAIR.unfence", sql_head=self._preview(sql, 100))
        return sql

    # --------- Execution & Safety ---------
    def _is_select_only(self, sql: str) -> bool:
        s = sql.strip().lower()
        return s.startswith("select") or s.startswith("with")

    def _strip_sql_comments(self, sql: str) -> str:
        # Remove block and line comments for scanning
        no_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        no_line = re.sub(r"--.*?$", " ", no_block, flags=re.M)
        return no_line

    def _enforce_limit(self, sql: str, limit: int) -> str:
        s = sql.strip().rstrip(";")
        scan_compact = re.sub(r"\s+", " ", self._strip_sql_comments(s))
        if re.search(r"\blimit\b", scan_compact, flags=re.I):
            self._log_step("LIMIT.detected")
            return s
        self._log_step("LIMIT.append", limit=int(limit))
        return f"{s}\nLIMIT {int(limit)}"

    def _execute_sql(self, sql: str, limit: int) -> Tuple[List[str], List[List[Any]]]:
        if not self._is_select_only(sql):
            raise ValueError("Only SELECT/WITH queries are allowed.")
        lower = sql.lower()
        for tok in FORBIDDEN_TOKENS:
            if tok in lower and tok != ";":
                raise ValueError("Forbidden token detected in SQL.")
        if ";" in sql.strip().rstrip(";"):
            raise ValueError("Multiple statements are not allowed.")
        final_sql = self._enforce_limit(sql, limit or 100)
        self._log_step("EXEC.start", preview=self._preview(sql, 120))
        self._log_step("EXEC.final_sql", head=self._preview(final_sql, 160))

        conn = sqlite3.connect(READ_ONLY_URI, uri=True)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            try:
                cur.execute(final_sql)
                rows = cur.fetchall()
            except sqlite3.Error as e:
                self._log_step("EXEC.error", message=str(e))
                raise ValueError(f"SQLite error: {e}") from e
            columns = [d[0] for d in cur.description] if cur.description else []
            result_rows = [list(r) for r in rows]
            return columns, result_rows
        finally:
            conn.close()

    # --------- Parser for UI struct ---------
    def _to_structured_table_dict(self, text: str) -> dict:
        name = None
        desc = None
        columns: List[dict] = []

        m_name = re.search(r"Table:\s*([A-Za-z0-9_]+)", text, flags=re.IGNORECASE)
        if m_name:
            name = m_name.group(1).strip()

        m_desc = re.search(r"Description:\s*([\s\S]*?)(?:\n\s*Columns:|$)", text, flags=re.IGNORECASE)
        if m_desc:
            desc = m_desc.group(1).strip()

        m_cols = re.search(r"Columns:\s*([\s\S]*)", text, flags=re.IGNORECASE)
        if m_cols:
            lines = [l.strip() for l in m_cols.group(1).splitlines() if l.strip()]
            for line in lines:
                cm = re.match(r"^[-*]\s*(?:\[([^\]]+)\]\s*)?([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:—|-|:)\s*(.*)?$", line)
                if not cm:
                    cm = re.match(r"^[-*]\s*(?:\[([^\]]+)\]\s*)?([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*$", line)
                if cm:
                    keys_raw = (cm.group(1) or '').strip()
                    col_name = cm.group(2)
                    type_raw = (cm.group(3) or '').strip()
                    comment = (cm.group(4) or '').strip()
                    nullable = 'NOT NULL' if re.search(r"NOT\s+NULL", type_raw, flags=re.IGNORECASE) else ''
                    type_clean = re.sub(r"\bNOT\s+NULL\b", "", type_raw, flags=re.IGNORECASE).strip().strip(',')
                    columns.append({
                        'key': keys_raw,
                        'name': col_name,
                        'type': type_clean,
                        'nullable': nullable,
                        'comment': comment,
                    })

        return {
            'table': name or '(unknown)',
            'description': desc or '',
            'columns': columns,
        }

    # --------- Helpers ---------
    def _extract_table_names_preview(self, texts: List[str]) -> str:
        names: List[str] = []
        for t in texts:
            m = re.search(r"Table:\s*([A-Za-z0-9_]+)", t, flags=re.IGNORECASE)
            if m:
                names.append(m.group(1))
        if not names:
            return "(none)"
        return ", ".join(names[:5]) + ("…" if len(names) > 5 else "")

    def _extract_tables_from_sql(self, sql: str) -> set[str]:
        """Heuristically extract table names from FROM/JOIN clauses.

        This is a lightweight regex-based approach good enough for guard checks. It ignores subqueries.
        """
        try:
            s = self._strip_sql_comments(sql or "")
            # collapse whitespace
            s = re.sub(r"\s+", " ", s)
            tables: set[str] = set()
            # Find FROM <table> and JOIN <table> tokens not followed immediately by '(' (i.e., subquery)
            for kw in ("from", "join"):
                pattern = re.compile(rf"\b{kw}\s+([A-Za-z_][A-Za-z0-9_\.]*)(?!\s*\()", flags=re.IGNORECASE)
                for m in pattern.finditer(s):
                    raw = m.group(1)
                    # strip potential schema prefix and quotes
                    name = raw.split(".")[-1].strip().strip("`\"[]")
                    if name:
                        tables.add(name)
            return tables
        except Exception:
            return set()
