"""
API Routes for DeepResearcher
Provides:
  - POST /api/v1/research/stream — SSE streaming for the main LangGraph agent.
  - POST /api/v1/chat           — Lightweight follow-up Q&A against an existing dossier.
"""
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.agent.graph import research_agent
from app.agent.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Topic, question, or message to research")
    max_iterations: int = Field(default=2, ge=1, le=3, description="Maximum reflection loops")


class FollowUpRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Follow-up question about the dossier")
    dossier: str = Field(default="", description="The previously generated Markdown dossier (context)")
    topic: str = Field(default="", description="Original research topic for context")


async def _sse_generator(topic: str, max_iterations: int) -> AsyncGenerator[str, None]:
    """
    Executes the LangGraph research agent and yields SSE-formatted events.
    Format:
        event: <event_name>\n
        data: <json_string>\n\n
    """
    initial_state = {
        "topic": topic,
        "plan_queries": [],
        "search_queries": [],
        "sources": [],
        "critique": "",
        "gaps_found": False,
        "iteration": 1,
        "max_iterations": max_iterations,
        "format_style": "executive_brief",
        "final_report": "",
        "needs_clarification": False,
        "status_message": f"Starting research for: '{topic}'",
    }

    # Emit initial event
    yield f"event: start\ndata: {json.dumps({'message': initial_state['status_message']})}\n\n"

    try:
        for event in research_agent.stream(initial_state):
            for node_name, node_output in event.items():
                status_msg = node_output.get("status_message", f"Completed {node_name}")
                payload = {
                    "node": node_name,
                    "status_message": status_msg,
                }

                if node_name == "planner":
                    payload["queries"] = node_output.get("plan_queries", [])
                    yield f"event: planner\ndata: {json.dumps(payload)}\n\n"

                    # If input was conversational/ambiguous, yield clarification response immediately
                    if node_output.get("needs_clarification"):
                        clarification_payload = {
                            "node": "planner",
                            "status_message": status_msg,
                            "report": node_output.get("final_report", ""),
                        }
                        yield f"event: report\ndata: {json.dumps(clarification_payload)}\n\n"

                elif node_name == "searcher":
                    payload["sources"] = node_output.get("sources", [])
                    yield f"event: searcher\ndata: {json.dumps(payload)}\n\n"

                elif node_name == "critic":
                    payload["critique"] = node_output.get("critique", "")
                    payload["gaps_found"] = node_output.get("gaps_found", False)
                    payload["refined_queries"] = node_output.get("search_queries", [])
                    yield f"event: critic\ndata: {json.dumps(payload)}\n\n"

                elif node_name == "synthesizer":
                    payload["report"] = node_output.get("final_report", "")
                    yield f"event: report\ndata: {json.dumps(payload)}\n\n"

        yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"

    except Exception as exc:
        logger.exception("Error during research stream: %s", exc)
        err_payload = {"error": str(exc), "status": "failed"}
        yield f"event: error\ndata: {json.dumps(err_payload)}\n\n"


@router.post("/research/stream")
async def stream_research(req: ResearchRequest):
    """
    Stream live agent research events via Server-Sent Events (SSE).
    """
    return StreamingResponse(
        _sse_generator(req.topic, req.max_iterations),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat")
async def follow_up_chat(req: FollowUpRequest):
    """
    Lightweight follow-up Q&A endpoint.
    Uses the existing dossier + original topic as context — no new web searches.
    Returns a JSON object: { "answer": "<markdown string>" }
    """
    system_prompt = (
        "You are DeepResearcher, an expert research assistant. "
        "The user has just finished reading a research dossier and has a follow-up question. "
        "Answer it concisely and accurately in Markdown, using the dossier context provided. "
        "If the question asks for code, provide a clean, well-commented code block. "
        "If the question asks for a diagram, write a Mermaid flowchart inside a ```mermaid block. "
        "If the dossier context is insufficient, draw on your domain knowledge and say so briefly."
    )

    context_block = ""
    if req.dossier:
        # Truncate dossier to avoid token overflow (keep first ~6000 chars)
        trimmed = req.dossier[:6000]
        context_block = f"\n\n---\n## Dossier Context (truncated):\n{trimmed}\n---\n"

    user_msg = (
        f"Original Research Topic: {req.topic or 'Unknown'}"
        f"{context_block}\n\n"
        f"Follow-up Question: {req.question}"
    )

    try:
        llm = get_llm(temperature=0.2)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ])
        return JSONResponse(content={"answer": response.content})
    except Exception as exc:
        logger.exception("Follow-up chat error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "answer": ""},
        )
