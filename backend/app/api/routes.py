"""
API Routes for DeepResearcher
Provides Server-Sent Events (SSE) streaming endpoint for live agent research.
"""
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import research_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Topic or question to research")
    max_iterations: int = Field(default=2, ge=1, le=3, description="Maximum reflection loops")


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
        "final_report": "",
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
