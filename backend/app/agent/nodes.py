"""
LangGraph Nodes for DeepResearcher
Defines the functional nodes: Planner, Searcher, Critic, and Synthesizer.
Includes strict query sanitization and relevance filtering.
"""
import json
import logging
import re
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from app.agent.state import ResearchState, SourceItem
from app.agent.llm_factory import get_llm
from app.tools.search import search_web
from app.config import get_settings

logger = logging.getLogger(__name__)


def _sanitize_query(q: str, topic: str) -> str:
    """
    Guarantees search queries are anchored to the core topic.
    Prevents ambiguous single-word queries (e.g., 'future', 'pricing') from returning irrelevant noise.
    """
    clean = q.strip().strip('"').strip("'")
    words = clean.split()

    # Extract meaningful keywords from topic
    topic_keywords = [
        w.lower() for w in re.findall(r'\b[A-Za-z0-9_]{3,}\b', topic)
        if w.lower() not in {"the", "for", "and", "vs", "versus", "with", "into"}
    ]

    has_topic_match = any(kw in clean.lower() for kw in topic_keywords[:4])

    # If query is too short or doesn't mention the subject, anchor it with topic prefix
    if len(words) <= 2 or not has_topic_match:
        anchor = " ".join(topic.split()[:4])
        anchored = f"{anchor} {clean}".strip()
        logger.info("Anchored ambiguous query '%s' -> '%s'", clean, anchored)
        return anchored

    return clean


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
    Decomposes the user's research topic into targeted, anchored search queries.
    """
    topic = state["topic"]
    logger.info("PlannerNode: generating queries for topic: '%s'", topic)

    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(QueryPlan)

    system_prompt = (
        "You are an expert research planner. Given a topic or question, generate 3 to 4 targeted, "
        "diverse web search queries. Avoid vague queries; include concrete keywords, comparison terms, "
        "and technical or industry terminology.\n"
        "CRITICAL RULE: Every single query MUST explicitly contain the core subject nouns of the topic "
        "(e.g., 'PostgreSQL', 'SQLite', etc.). NEVER output isolated single words like 'future', 'pricing', 'overview', or 'comparison'."
    )

    plan: QueryPlan = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research Topic: {topic}"),
    ])

    raw_queries = [q.strip() for q in plan.queries if q.strip()]
    sanitized_queries = [_sanitize_query(q, topic) for q in raw_queries]
    logger.info("PlannerNode generated %d queries: %s", len(sanitized_queries), sanitized_queries)

    return {
        "plan_queries": sanitized_queries,
        "search_queries": sanitized_queries,
        "iteration": 1,
        "max_iterations": state.get("max_iterations", 2),
        "status_message": f"Planned {len(sanitized_queries)} targeted search queries.",
    }


# ---------------------------------------------------------------------------
# Node 2: Searcher
# ---------------------------------------------------------------------------
def search_node(state: ResearchState) -> dict:
    """
    Executes current search_queries and aggregates unique sources.
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
    Evaluates accumulated sources against the topic.
    Guarantees follow-up queries are anchored and non-ambiguous.
    """
    topic = state["topic"]
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 2)
    sources = state.get("sources", [])

    logger.info("CriticNode: evaluating iteration %d of %d", iteration, max_iterations)

    if iteration >= max_iterations:
        return {
            "gaps_found": False,
            "critique": "Reached maximum research iterations. Proceeding to report synthesis.",
            "search_queries": [],
            "status_message": "Completed research iterations. Proceeding to synthesis.",
        }

    sources_summary = "\n".join(
        f"- [{s['title']}]: {s['snippet']} (URL: {s['url']})"
        for s in sources[:15]
    )

    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(CritiqueDecision)

    system_prompt = (
        "You are an objective research critic evaluating gathered web evidence against a research objective. "
        "Determine if the current findings sufficiently cover the topic, or if critical gaps, specific metrics, "
        "or perspectives are missing.\n"
        "CRITICAL RULES FOR FOLLOW-UP QUERIES:\n"
        "1. Every follow-up query MUST be specific and explicitly include the core topic subject keywords (e.g., 'PostgreSQL SQLite memory usage at edge').\n"
        "2. NEVER output vague, generic, or single-word search queries like 'Future', 'Costs', 'Performance', 'Overview', or 'Architecture'.\n"
        "3. If gathered evidence contains zero relevant sources or off-topic results, provide full, explicit search queries directly restating the core subject."
    )

    user_msg = (
        f"Research Topic: {topic}\n\n"
        f"Gathered Evidence ({len(sources)} sources):\n{sources_summary or 'No sources gathered yet.'}\n\n"
        "Evaluate sufficiency."
    )

    decision: CritiqueDecision = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    if decision.has_gaps and decision.follow_up_queries:
        sanitized_followups = [_sanitize_query(fq, topic) for fq in decision.follow_up_queries if fq.strip()]
        logger.info("CriticNode: gaps identified. Refining %d queries for iteration %d: %s", len(sanitized_followups), iteration + 1, sanitized_followups)
        return {
            "gaps_found": True,
            "critique": decision.critique,
            "search_queries": sanitized_followups,
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
    Synthesizes evidence and deep technical knowledge into an executive Markdown dossier.
    Filters out off-topic noise and ensures technical comparative tables are populated.
    """
    topic = state["topic"]
    sources = state.get("sources", [])

    logger.info("SynthesizerNode: generating final report from %d sources", len(sources))

    evidence_text = "\n\n".join(
        f"Source [{i+1}]: {s['title']}\nURL: {s['url']}\nSnippet: {s['snippet']}"
        for i, s in enumerate(sources)
    )

    system_prompt = """You are a senior technical research analyst. 
Your task is to synthesize an executive-grade, comprehensive Markdown research dossier on the requested topic based on gathered evidence and deep domain knowledge.

CRITICAL EVIDENCE & RELEVANCE RULES:
1. RELEVANCE FILTERING: Carefully inspect the provided evidence. If any source is completely off-topic, noise, or irrelevant (e.g. songs, pop culture, unrelated products), IGNORE and EXCLUDE it completely. Do not mention or cite irrelevant noise in the report.
2. TECHNICAL COMPLETENESS: If live web search evidence was sparse, incomplete, or blocked by upstream search engines, you MUST synthesize your comprehensive technical knowledge of the subject (e.g., PostgreSQL vs SQLite architecture, embedded footprints, concurrency, SQLite WAL vs Postgres MVCC, replication engines like LiteFS / ElectricSQL, edge deployment patterns) to produce a thorough, high-value technical comparison.
3. DATA TABLE INTEGRITY: NEVER leave the comparative table empty or filled with 'No data available in sources'. Provide the factual, industry-standard comparative matrix based on real architectural benchmarks and specifications.
4. If web retrieval had sparse coverage, add an executive note:
   '> **Note on Evidence Retrieval**: Live web evidence had partial coverage; supplemented with established architectural specifications and system design benchmarks.'

Formatting Requirements:
1. # <Title of Research Dossier>
2. ## Executive Summary (High-level overview of key answers, trade-offs, and takeaways)
3. ## Detailed Findings & Thematic Analysis (In-depth analysis grouped into logical sub-topics)
4. ## Comparative Breakdown / Data Table (Comprehensive Markdown table comparing key technical criteria)
5. ## Strategic Implications & Future Outlook (Specific to the target environment/domain)
6. ## Sources & References (List all relevant technical sources with clickable markdown links in format: - [Title](URL))
"""

    user_msg = f"Research Topic: {topic}\n\nGathered Evidence:\n{evidence_text or 'No direct web snippets available.'}\n\nWrite the comprehensive research dossier:"

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
