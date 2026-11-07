"""
LangGraph Nodes for DeepResearcher
Defines the functional nodes: Planner, Searcher, Critic, and Synthesizer.
Ensures search queries are natural, self-contained phrases without artificial string concatenation.
"""
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
        description="List of 3 to 4 complete, natural web search queries to research the topic thoroughly. Each query must be a natural search phrase of at least 3 words."
    )


class CritiqueDecision(BaseModel):
    has_gaps: bool = Field(
        description="True if critical aspects, data points, or viewpoints are missing from the gathered evidence. False if gathered info is sufficient."
    )
    critique: str = Field(
        description="Detailed explanation of what information is present, what is missing, and whether additional searches are genuinely required."
    )
    follow_up_queries: list[str] = Field(
        default_factory=list,
        description="1 to 2 complete, self-contained search engine queries (minimum 3 words each) targeting specific missing facts. Never output single words, category labels, or topic names like 'future', 'costs', or 'performance'."
    )


# ---------------------------------------------------------------------------
# Node 1: Planner
# ---------------------------------------------------------------------------
def planner_node(state: ResearchState) -> dict:
    """
    Decomposes the user's research topic into targeted, natural search queries.
    """
    topic = state["topic"]
    logger.info("PlannerNode: generating queries for topic: '%s'", topic)

    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(QueryPlan)

    system_prompt = (
        "You are an expert research planner. Given a research objective, decompose it into 3 to 4 specific, "
        "natural web search queries that an engineer or analyst would enter into a search engine.\n"
        "Each query must be a complete, natural search phrase (minimum 3 words) exploring different dimensions "
        "(e.g., technical trade-offs, architecture, performance benchmarks, real-world adoption).\n"
        "NEVER output single words, category titles, or abstract tags."
    )

    plan: QueryPlan = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research Topic: {topic}"),
    ])

    raw_queries = [q.strip().strip('"').strip("'") for q in plan.queries if q.strip()]
    valid_queries = [q for q in raw_queries if len(q.split()) >= 3]
    if not valid_queries:
        valid_queries = [topic]

    logger.info("PlannerNode generated %d queries: %s", len(valid_queries), valid_queries)

    return {
        "plan_queries": valid_queries,
        "search_queries": valid_queries,
        "iteration": 1,
        "max_iterations": state.get("max_iterations", 2),
        "status_message": f"Planned {len(valid_queries)} targeted search queries.",
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
    Validates that any follow-up queries are complete, self-contained search phrases.
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
        "You are an objective technical research critic evaluating gathered web evidence against a research objective.\n"
        "Evaluate whether the accumulated evidence adequately answers the topic or if critical technical gaps remain.\n"
        "CRITICAL RULES FOR FOLLOW-UP QUERIES:\n"
        "1. Every follow-up query MUST be a complete, self-contained search phrase that an engineer would type into Google (minimum 3 words).\n"
        "2. Do NOT output single-word category tags like 'future', 'costs', 'pricing', or 'performance'.\n"
        "3. If no further search is needed, set has_gaps=False."
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

    valid_followups = []
    if decision.has_gaps and decision.follow_up_queries:
        for fq in decision.follow_up_queries:
            clean_fq = fq.strip().strip('"').strip("'")
            # Only accept complete, natural search phrases
            if len(clean_fq.split()) >= 3:
                valid_followups.append(clean_fq)
            else:
                logger.warning("Discarded invalid query fragment '%s' (not a complete search query)", clean_fq)

    if valid_followups:
        logger.info("CriticNode: gaps identified. Formulated %d targeted queries for iteration %d: %s", len(valid_followups), iteration + 1, valid_followups)
        return {
            "gaps_found": True,
            "critique": decision.critique,
            "search_queries": valid_followups,
            "iteration": iteration + 1,
            "status_message": f"Identified knowledge gaps: {decision.critique[:90]}...",
        }
    else:
        logger.info("CriticNode: no valid follow-up queries required. Moving to synthesis.")
        return {
            "gaps_found": False,
            "critique": decision.critique if decision.has_gaps else "Information is comprehensive. Ready to synthesize dossier.",
            "search_queries": [],
            "status_message": "Proceeding to executive report synthesis.",
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
