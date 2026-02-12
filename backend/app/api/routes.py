from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.models.schemas import (
    GenerateRequest,
    GenerateResponse,
    BasicRequest,
    BasicResponse,
    CodeReviewResponse,
    FpfRagRequest,
    FpfRagResponse,
    ChemblSqlPlanRequest,
    ChemblSqlEditRequest,
    ChemblSqlEditResponse,
    ChemblSqlReexecuteRequest,
    ChemblSqlReexecuteResponse,
    ChemblSqlDownloadRequest,
    CodeReviewByUrlRequest,
)
from app.services.llm_model import LLMModel
from app.core.config import get_settings
from typing import Any
from app.services.github_app import GitHubApp
from app.services.code_review_controller import CodeReviewController
from app.core.logger import get_logger

router = APIRouter()
log = get_logger(__name__)
settings = get_settings()
llm = LLMModel()
github_app = GitHubApp()
code_review = CodeReviewController(llm, github_app)

@router.get("/")
def root():
    log.info("Root endpoint hit")
    return {"message": "Welcome to the GenAI API. Use /generate, /tests, or /docs endpoints."}

@router.post("/generate", response_model=GenerateResponse)
async def generate_code(payload: GenerateRequest):
    log.info("[QUERY][generate] lang=%s prompt.len=%d", payload.language, len(payload.prompt or ""))
    text = llm.generate_code(payload.prompt, payload.language, payload.api_key)
    return GenerateResponse(code=text, language=payload.language)


@router.post("/tests", response_model=BasicResponse)
async def generate_tests(payload: BasicRequest):
    log.info("[QUERY][tests] code.len=%d", len(payload.code or ""))
    text = llm.generate_tests(payload.code)
    return BasicResponse(code=text)

@router.post("/docs", response_model=BasicResponse)
async def generate_docs(payload: BasicRequest):
    log.info("[QUERY][docs] code.len=%d", len(payload.code or ""))
    text = llm.generate_docs(payload.code)
    return BasicResponse(code=text)


@router.post("/code-review/webhook", response_model=CodeReviewResponse)
async def code_review_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Webhook for PR reviews: verifies signature, generates review, posts using PAT."""
    raw_body: bytes = await request.body()
    # Verify signature if configured. If invalid, return a 200 JSON response GitHub accepts, but skip processing.
    if not code_review.signature_valid(dict(request.headers), raw_body):
        return CodeReviewResponse(review="signature_invalid: ignored")

    # Pull optional 'payload' from query or form for proxies that wrap JSON
    payload_str = request.query_params.get("payload")
    if payload_str is None:
        try:
            form = await request.form()
            payload_str = form.get("payload") if form else None
        except RuntimeError:
            # form() may raise in some server contexts (e.g., non-form content-type)
            payload_str = None
    payload_obj = code_review.parse_payload(raw_body, payload_str)
    ctx = code_review.extract_pr_context(payload_obj)
    action = (ctx.get("action") or "").lower()
    title = ctx["title"]
    base_branch = ctx.get("base_branch")
    head_branch = ctx.get("head_branch")
    diff_url = ctx.get("diff_url")
    diff_summary = code_review.diff_summary(ctx)

    def _run_review_task() -> None:
        review_text = code_review.generate_review_text(title, ctx.get("body", ""), diff_summary)
        log.info("[CODE-REVIEW] Generated review for: %s", title)
        code_review.try_post_review(ctx, review_text)
        log.info(
            "[CODE-REVIEW] Post attempted on %s/%s#%s",
            ctx.get("owner"),
            ctx.get("repo"),
            ctx.get("pr_number"),
        )

    # Only trigger for PR opened or reopened
    if action in {"opened", "reopened"}:
        background_tasks.add_task(_run_review_task)

    ack = (
        f"ok: pr={title} base={base_branch or '-'} head={head_branch or '-'}"
        + (" diff" if diff_url else "")
        + (" bot" if ctx.get("installation_id") else "")
        + (f" action={action}" if action else "")
        + (" queued" if action in {"opened", "reopened"} else " skipped")
    )
    return CodeReviewResponse(review=ack)

@router.post("/code-review/by-url", response_model=CodeReviewResponse)
async def code_review_by_url(payload: CodeReviewByUrlRequest):
    """Trigger a PR review by providing a GitHub Pull Request URL.

    Accepts URLs like:
      - https://github.com/<owner>/<repo>/pull/<number>
      - https://github.com/<owner>/<repo>/pull/<number>/files
    """
    log.info("[QUERY][code-review/by-url] url=%s", payload.url)
    import re
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:/.*)?$", payload.url.strip())
    if not m:
        raise HTTPException(status_code=422, detail="Provide a valid GitHub PR URL: https://github.com/<owner>/<repo>/pull/<number>")
    owner, repo, pr_number = m.group(1), m.group(2), int(m.group(3))

    # Build context mimicking webhook payload
    ctx = {
        "action": "opened",
        "title": f"PR #{pr_number}",
        "body": "",
        "base_branch": None,
        "head_branch": None,
        "diff_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}.diff",
        "repository_full": f"{owner}/{repo}",
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "installation_id": None,
    }
    diff_summary = code_review.diff_summary(ctx)
    review_text = code_review.generate_review_text(ctx["title"], ctx.get("body", ""), diff_summary)
    code_review.try_post_review(ctx, review_text)
    return CodeReviewResponse(review=f"queued: {owner}/{repo}#{pr_number}")

# Unofficial Food Packaging Forum Chatbot (new path)
@router.post("/fpf-chatbot/chat", response_model=FpfRagResponse)
async def fpf_rag_chat(payload: FpfRagRequest):
    log.info("[QUERY][fpf-chatbot] config=%s prompt.len=%d", payload.config_key, len(payload.prompt or ""))
    text = llm.generate_rag_response(payload.prompt, payload.api_key, payload.config_key)
    return FpfRagResponse(reply=text)

# ChEMBL Agent (new paths)
@router.post("/chembl-agent/run", response_model=dict)
async def chembl_run(payload: ChemblSqlPlanRequest):
    """End-to-end run: plan → retrieve → synthesize → execute.

    Returns: { sql, related_tables, columns, rows, retries, repaired, no_context, not_chembl, chembl_reason }
    """
    log.info("[QUERY][chembl/run] prompt.len=%d", len(payload.prompt or ""))
    try:
        state: dict[str, Any] = llm.run_chembl_full(payload.prompt, limit=100, api_key=payload.api_key)
        # Attach prompt and persist session if memory_id provided
        state["prompt"] = payload.prompt
        if getattr(payload, "memory_id", None):
            llm.chembl_session_set(payload.memory_id, state)
        response = {
            "sql": state.get("sql", ""),
            "related_tables": state.get("structured_tables", []),
            "columns": state.get("columns", []),
            "rows": state.get("rows", []),
            "retries": state.get("retries", 0),
            "repaired": bool(state.get("retries", 0) > 0),
            "no_context": bool(state.get("no_context", False)),
            "not_chembl": bool(state.get("not_chembl", False)),
            "chembl_reason": state.get("chembl_reason", ""),
            "optimized_guidelines": state.get("optimized_guidelines", ""),
            "memory_id": payload.memory_id or None,
        }
        log.debug(
            "[CHEMBL][run] response summary: cols=%d rows=%d retries=%d repaired=%s",
            len(response.get("columns", [])),
            len(response.get("rows", [])),
            int(response.get("retries", 0)),
            bool(response.get("repaired", False)),
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/chembl-agent/edit", response_model=ChemblSqlEditResponse)
async def chembl_edit(payload: ChemblSqlEditRequest):
    """Apply a tweak to the last SQL for a session and return updated SQL/results."""
    # Ensure model running with api key
    llm.check_model_running(payload.api_key)
    state = llm.chembl_apply_edit(payload.memory_id, payload.instruction, payload.api_key, prev_sql=getattr(payload, "prev_sql", None))
    return ChemblSqlEditResponse(
        sql=state.get("sql", ""),
        related_tables=state.get("structured_tables", []),
        columns=state.get("columns", []),
        rows=state.get("rows", []),
        retries=int(state.get("retries") or 0),
        repaired=bool(state.get("repaired") or False),
        no_context=bool(state.get("no_context") or False),
        not_chembl=bool(state.get("not_chembl") or False),
        chembl_reason=state.get("chembl_reason") or "",
        optimized_guidelines=state.get("optimized_guidelines") or "",
    )


@router.post("/chembl-agent/reexecute", response_model=ChemblSqlReexecuteResponse)
async def chembl_reexecute(payload: ChemblSqlReexecuteRequest):
    """Re-execute the last SQL for a given session with a new LIMIT."""
    # Ensure model running with api key
    llm.check_model_running(payload.api_key)
    prev = llm.chembl_session_get(payload.memory_id)
    if not prev:
        raise HTTPException(status_code=400, detail="Unknown memory_id; run a query first.")
    sql = (prev.get("sql") or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="No SQL present for this session.")
    cols, rows = llm.chembl_reexecute(payload.memory_id, payload.limit, payload.api_key)
    return ChemblSqlReexecuteResponse(columns=cols, rows=rows)


@router.post("/chembl-agent/download")
async def chembl_download(payload: ChemblSqlDownloadRequest):
    """Download full results by re-executing session SQL without LIMIT.

    Uses a streaming CSV response to avoid large in-memory payloads.
    """
    llm.check_model_running(payload.api_key)
    prev = llm.chembl_session_get(payload.memory_id)
    if not prev:
        raise HTTPException(status_code=400, detail="Unknown memory_id; run a query first.")
    sql = (prev.get("sql") or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="No SQL present for this session.")

    # Ensure pipeline exists
    if not llm.chembl_pipeline:
        from app.services.chembl_sql_pipeline import ChemblSqlPipeline
        llm.chembl_pipeline = ChemblSqlPipeline(llm.llm, llm.vector_store_sql)

    def _iter_bytes():
        # limit=-1: remove any existing LIMIT and apply none
        yield from llm.chembl_pipeline.stream_csv(sql, limit=-1, chunk_rows=2000)

    filename = f"chembl_query_{payload.memory_id}_full.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(_iter_bytes(), media_type="text/csv; charset=utf-8", headers=headers)
