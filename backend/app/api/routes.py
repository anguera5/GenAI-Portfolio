from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
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
    log.info("[USER_ACTION][generate] lang=%s prompt.len=%d", payload.language, len(payload.prompt or ""))
    try:
        text = llm.generate_code(payload.prompt, payload.language, payload.api_key)
        log.info("[SUCCESS][generate] lang=%s response.len=%d", payload.language, len(text or ""))
        return GenerateResponse(code=text, language=payload.language)
    except Exception as e:
        log.error("[ERROR][generate] lang=%s error=%s", payload.language, str(e), exc_info=True)
        raise


@router.post("/tests", response_model=BasicResponse)
async def generate_tests(payload: BasicRequest):
    log.info("[USER_ACTION][tests] code.len=%d", len(payload.code or ""))
    try:
        text = llm.generate_tests(payload.code)
        log.info("[SUCCESS][tests] response.len=%d", len(text or ""))
        return BasicResponse(code=text)
    except Exception as e:
        log.error("[ERROR][tests] error=%s", str(e), exc_info=True)
        raise

@router.post("/docs", response_model=BasicResponse)
async def generate_docs(payload: BasicRequest):
    log.info("[USER_ACTION][docs] code.len=%d", len(payload.code or ""))
    try:
        text = llm.generate_docs(payload.code)
        log.info("[SUCCESS][docs] response.len=%d", len(text or ""))
        return BasicResponse(code=text)
    except Exception as e:
        log.error("[ERROR][docs] error=%s", str(e), exc_info=True)
        raise


@router.post("/code-review/webhook", response_model=CodeReviewResponse)
async def code_review_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Webhook for PR reviews: verifies signature, generates review, posts using PAT."""
    log.info("[USER_ACTION][code-review/webhook] Received webhook request")
    raw_body: bytes = await request.body()
    # Verify signature if configured. If invalid, return a 200 JSON response GitHub accepts, but skip processing.
    if not code_review.signature_valid(dict(request.headers), raw_body):
        log.warning("[SECURITY][code-review/webhook] Invalid signature detected")
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
    
    log.info(
        "[USER_ACTION][code-review/webhook] PR details: title=%s action=%s base=%s head=%s",
        title, action, base_branch, head_branch
    )

    def _run_review_task() -> None:
        try:
            review_text = code_review.generate_review_text(title, ctx.get("body", ""), diff_summary)
            log.info("[SUCCESS][code-review/webhook] Generated review for: %s", title)
            code_review.try_post_review(ctx, review_text)
            log.info(
                "[SUCCESS][code-review/webhook] Post attempted on %s/%s#%s",
                ctx.get("owner"),
                ctx.get("repo"),
                ctx.get("pr_number"),
            )
        except Exception as e:
            log.error(
                "[ERROR][code-review/webhook] Failed to generate/post review: %s",
                str(e),
                exc_info=True
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
    log.info("[SUCCESS][code-review/webhook] Response: %s", ack)
    return CodeReviewResponse(review=ack)

@router.post("/code-review/by-url", response_model=CodeReviewResponse)
async def code_review_by_url(payload: CodeReviewByUrlRequest):
    """Trigger a PR review by providing a GitHub Pull Request URL.

    Accepts URLs like:
      - https://github.com/<owner>/<repo>/pull/<number>
      - https://github.com/<owner>/<repo>/pull/<number>/files
    """
    log.info("[USER_ACTION][code-review/by-url] url=%s", payload.url)
    import re
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:/.*)?$", payload.url.strip())
    if not m:
        log.warning("[ERROR][code-review/by-url] Invalid URL format: %s", payload.url)
        raise HTTPException(status_code=422, detail="Provide a valid GitHub PR URL: https://github.com/<owner>/<repo>/pull/<number>")
    owner, repo, pr_number = m.group(1), m.group(2), int(m.group(3))
    
    log.info("[USER_ACTION][code-review/by-url] Processing PR: %s/%s#%d", owner, repo, pr_number)

    try:
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
        log.info("[SUCCESS][code-review/by-url] Review queued for: %s/%s#%d", owner, repo, pr_number)
        return CodeReviewResponse(review=f"queued: {owner}/{repo}#{pr_number}")
    except Exception as e:
        log.error("[ERROR][code-review/by-url] Failed to process PR review: %s", str(e), exc_info=True)
        raise

# Unofficial Food Packaging Forum Chatbot (new path)
@router.post("/fpf-chatbot/chat", response_model=FpfRagResponse)
async def fpf_rag_chat(payload: FpfRagRequest):
    log.info("[USER_ACTION][fpf-chatbot] config=%s prompt.len=%d", payload.config_key, len(payload.prompt or ""))
    try:
        text = llm.generate_rag_response(payload.prompt, payload.api_key, payload.config_key)
        log.info("[SUCCESS][fpf-chatbot] config=%s response.len=%d", payload.config_key, len(text or ""))
        return FpfRagResponse(reply=text)
    except Exception as e:
        log.error("[ERROR][fpf-chatbot] config=%s error=%s", payload.config_key, str(e), exc_info=True)
        raise

# ChEMBL Agent (new paths)
@router.post("/chembl-agent/run", response_model=dict)
async def chembl_run(payload: ChemblSqlPlanRequest):
    """End-to-end run: plan → retrieve → synthesize → execute.

    Returns: { sql, related_tables, columns, rows, retries, repaired, no_context, not_chembl, chembl_reason }
    """
    log.info("[USER_ACTION][chembl/run] prompt.len=%d", len(payload.prompt or ""))
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
        log.info(
            "[SUCCESS][chembl/run] response summary: cols=%d rows=%d retries=%d repaired=%s",
            len(response.get("columns", [])),
            len(response.get("rows", [])),
            int(response.get("retries", 0)),
            bool(response.get("repaired", False)),
        )
        return response
    except ValueError as e:
        log.error("[ERROR][chembl/run] ValueError: %s", str(e), exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error("[ERROR][chembl/run] Unexpected error: %s", str(e), exc_info=True)
        raise


@router.post("/chembl-agent/edit", response_model=ChemblSqlEditResponse)
async def chembl_edit(payload: ChemblSqlEditRequest):
    """Apply a tweak to the last SQL for a session and return updated SQL/results."""
    log.info("[USER_ACTION][chembl/edit] memory_id=%s instruction.len=%d", payload.memory_id, len(payload.instruction or ""))
    try:
        # Ensure model running with api key
        llm.check_model_running(payload.api_key)
        state = llm.chembl_apply_edit(payload.memory_id, payload.instruction, payload.api_key, prev_sql=getattr(payload, "prev_sql", None))
        log.info(
            "[SUCCESS][chembl/edit] memory_id=%s cols=%d rows=%d",
            payload.memory_id,
            len(state.get("columns", [])),
            len(state.get("rows", []))
        )
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
    except Exception as e:
        log.error("[ERROR][chembl/edit] memory_id=%s error=%s", payload.memory_id, str(e), exc_info=True)
        raise


@router.post("/chembl-agent/reexecute", response_model=ChemblSqlReexecuteResponse)
async def chembl_reexecute(payload: ChemblSqlReexecuteRequest):
    """Re-execute the last SQL for a given session with a new LIMIT."""
    log.info("[USER_ACTION][chembl/reexecute] memory_id=%s limit=%d", payload.memory_id, payload.limit)
    try:
        # Ensure model running with api key
        llm.check_model_running(payload.api_key)
        prev = llm.chembl_session_get(payload.memory_id)
        if not prev:
            log.warning("[ERROR][chembl/reexecute] Unknown memory_id: %s", payload.memory_id)
            raise HTTPException(status_code=400, detail="Unknown memory_id; run a query first.")
        sql = (prev.get("sql") or "").strip()
        if not sql:
            log.warning("[ERROR][chembl/reexecute] No SQL in session: %s", payload.memory_id)
            raise HTTPException(status_code=400, detail="No SQL present for this session.")
        cols, rows = llm.chembl_reexecute(payload.memory_id, payload.limit, payload.api_key)
        log.info("[SUCCESS][chembl/reexecute] memory_id=%s cols=%d rows=%d", payload.memory_id, len(cols), len(rows))
        return ChemblSqlReexecuteResponse(columns=cols, rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        log.error("[ERROR][chembl/reexecute] memory_id=%s error=%s", payload.memory_id, str(e), exc_info=True)
        raise
