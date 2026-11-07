"""
LangGraph Nodes for DeepResearcher
Defines the functional nodes: Planner, Searcher, Critic, and Synthesizer.
"""
import json
import logging
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from app.agent.state import ResearchState, SourceItem
from app.agent.llm_factory import get_llm
from app.tools.search import search_web
from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Schemas for Structured LLM Outputs
# ---------------------------------------------------------------------------
class QueryPlan(BaseModel):
    queries: list[str] = Field(
        description="List of 3 to 4 specific, diverse web search queries to research the topic thoroughly."
    )


class CritiqueDecision(BaseModel):
    has_gaps: bool = Field(
        description="True if critical aspects, data points, or viewpoints are missing. False if gathered info is sufficient."
    )
    critique: str = Field(
        description="Brief explanation of what information is present and what is missing."
    )
    follow_up_queries: list[str] = Field(
        default_factory=list,
        description="1 to 2 targeted follow-up search queries to fill the identified gaps (empty if has_gaps is False)."
    )


# ---------------------------------------------------------------------------
# Node 1: Planner
# ---------------------------------------------------------------------------
def planner_node(state: ResearchState) -> dict:
    """
    Decomposes the user's research topic into targeted search queries.
    """
    topic = state["topic"]
    logger.info("PlannerNode: generating queries for topic: '%s'", topic)

    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(QueryPlan)

    system_prompt = (
        "You are an expert research planner. Given a topic or question, generate 3 to 4 targeted, "
        "diverse web search queries. Avoid vague queries; include concrete keywords, comparison terms, "
        "and technical or industry terminology."
    )
    
    plan: QueryPlan = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research Topic: {topic}"),
    ])

    queries = [q.strip() for q in plan.queries if q.strip()]
    logger.info("PlannerNode generated %d queries: %s", len(queries), queries)

    return {
        "plan_queries": queries,
        "search_queries": queries,
        "iteration": 1,
        "max_iterations": state.get("max_iterations", 2),
        "status_message": f"Planned {len(queries)} research search queries.",
    }


# ---------------------------------------------------------------------------
# Node 2: Searcher
# ---------------------------------------------------------------------------
def search_node(state: ResearchState) -> dict:
    """
    Executes current search_queries on DuckDuckGo and aggregates unique sources.
    """
    queries = state.get("search_queries", [])
    existing_urls = {s["url"] for s in state.get("sources", [])}

    logger.info("SearchNode: executing %d queries", len(queries))
    new_sources: list[SourceItem] = []

    for q in queries:
        results = search_web(q, max_results=4)
        for r in results:
            if r["url"] not in existing_urls:
                existing_urls.add(r["url"])
                new_sources.append(SourceItem(
                    title=r["title"],
                    url=r["url"],
                    snippet=r["snippet"],
                ))

    logger.info("SearchNode: found %d new unique sources", len(new_sources))
    return {
        "sources": new_sources,
        "status_message": f"Found {len(new_sources)} new sources (total: {len(existing_urls)}).",
    }


# ---------------------------------------------------------------------------
# Node 3: Critic (Reflection & Gap Detection)
# ---------------------------------------------------------------------------
def critic_node(state: ResearchState) -> dict:
    """
    Evaluates the accumulated sources against the research topic to detect gaps.
    Decides whether to trigger another search loop or proceed to synthesis.
    """
    topic = state["topic"]
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 2)
    sources = state.get("sources", [])

    logger.info("CriticNode: evaluating iteration %d of %d", iteration, max_iterations)

    # Safety check: if reached max iterations, stop searching and synthesize
    if iteration >= max_iterations:
        return {
            "gaps_found": False,
            "critique": "Reached maximum research iterations. Proceeding to report synthesis.",
            "search_queries": [],
            "status_message": "Completed research iterations. Proceeding to synthesis.",
        }

    # Summarize sources for the critic LLM
    sources_summary = "\n".join(
        f"- [{s['title']}]: {s['snippet']} (URL: {s['url']})"
        for s in sources[:15]
    )

    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(CritiqueDecision)

    system_prompt = (
        "You are an objective research critic evaluating gathered web evidence against a research objective. "
        "Determine if the current findings sufficiently cover the topic, or if critical gaps, specific metrics, "
        "or perspectives are missing. If critical gaps exist, provide 1 to 2 targeted follow-up queries."
    )

    user_msg = (
        f"Research Topic: {topic}\n\n"
        f"Gathered Evidence ({len(sources)} sources):\n{sources_summary}\n\n"
        "Evaluate sufficiency."
    )

    decision: CritiqueDecision = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    if decision.has_gaps and decision.follow_up_queries:
        logger.info("CriticNode: gaps identified. Refining %d queries for iteration %d", len(decision.follow_up_queries), iteration + 1)
        return {
            "gaps_found": True,
            "critique": decision.critique,
            "search_queries": decision.follow_up_queries,
            "iteration": iteration + 1,
            "status_message": f"Identified knowledge gaps: {decision.critique[:90]}...",
        }
    else:
        logger.info("CriticNode: data sufficient. Moving to synthesis.")
        return {
            "gaps_found": False,
            "critique": decision.critique,
            "search_queries": [],
            "status_message": "Information is comprehensive. Ready to synthesize dossier.",
        }


# ---------------------------------------------------------------------------
# Node 4: Synthesizer
# ---------------------------------------------------------------------------
def synthesizer_node(state: ResearchState) -> dict:
    """
    Synthesizes all gathered evidence into an executive Markdown dossier with citations.
    """
    topic = state["topic"]
    sources = state.get("sources", [])

    logger.info("SynthesizerNode: generating final report from %d sources", len(sources))

    # Format sources for context injection
    evidence_text = "\n\n".join(
        f"Source [{i+1}]: {s['title']}\nURL: {s['url']}\nSnippet: {s['snippet']}"
        for i, s in enumerate(sources)
    )

    system_prompt = """You are a senior research analyst. 
Your task is to synthesize an executive-grade, comprehensive Markdown research dossier based on the gathered evidence.

Formatting Requirements:
1. # <Title of Research Dossier>
2. ## Executive Summary (High-level overview of key answers and takeaways)
3. ## Detailed Findings & Thematic Analysis (In-depth analysis grouped into logical sub-topics)
4. ## Comparative Breakdown / Data Table (Compare key players, technologies, or options in a clear Markdown table)
5. ## Strategic Implications & Future Outlook
6. ## Sources & References (List all sources with clickable markdown links in format: - [Title](URL))

Quality Guidelines:
- Ground all facts, numbers, and dates strictly in the provided evidence.
- Include inline hyperlinked citations where appropriate.
- Be thorough, objective, and professional.
"""

    user_msg = f"Research Topic: {topic}\n\nGathered Evidence:\n{evidence_text}\n\nWrite the comprehensive research dossier:"

    llm = get_llm(temperature=0.1)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    logger.info("SynthesizerNode: report generated (%d characters)", len(response.content))
    return {
        "final_report": response.content,
        "status_message": "Executive research dossier generated successfully.",
    }
