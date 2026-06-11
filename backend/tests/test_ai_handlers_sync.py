"""Regression guard for the AI-insight UI-freeze fix.

The LLM-backed route handlers call a *synchronous* blocking httpx.post to
Ollama (up to 300s). If they are declared `async def`, that blocking call runs
on the event loop and freezes every other request until generation finishes
(the "every page hangs while an insight generates" bug). Declaring them plain
`def` makes FastAPI run them in a worker threadpool, keeping the loop free.

This test fails if any of them is ever (re-)made `async`, so the freeze can't
silently regress.
"""
import inspect

from backend import main


def test_llm_backed_handlers_are_sync_not_async():
    handlers = [
        main.ai_narrative,
        main.ai_nlq,
        main.report_pptx_endpoint,
        main.report_pdf_endpoint,
    ]
    offenders = [h.__name__ for h in handlers if inspect.iscoroutinefunction(h)]
    assert not offenders, (
        f"These LLM-backed handlers must stay synchronous (def, not async def) so "
        f"their blocking Ollama call runs in the threadpool instead of freezing the "
        f"event loop: {offenders}"
    )
