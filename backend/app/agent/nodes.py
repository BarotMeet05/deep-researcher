"""
LangGraph Nodes for DeepResearcher
Defines the functional nodes: Planner, Searcher, Critic, and Synthesizer.
Includes conversational intent evaluation and clarification prompting.
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
class ResearchTopicEvaluation(BaseModel):
    is_valid_topic: bool = Field(
        description="True if the input is a genuine topic, technical question, domain inquiry, or comparison that can be investigated. False if it is a greeting (e.g. 'hi', 'hello'), conversational chatter, or too underspecified to research."
    )
    clarification_message: str = Field(
        default="",
        description="If is_valid_topic is False, a polite, conversational response explaining what DeepResearcher is and prompting the user with 2-3 concrete example research inquiries."
    )
    search_queries: list[str] = Field(
        default_factory=list,
        description="If is_valid_topic is True, 3 to 4 natural, diverse web search queries exploring different aspects of the topic."
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
        description="Specific, targeted follow-up search queries to fill the identified gaps. Empty if has_gaps is False."
    )


# ---------------------------------------------------------------------------
# Node 1: Planner & Intent Evaluator
# ---------------------------------------------------------------------------
def planner_node(state: ResearchState) -> dict:
    """
    Evaluates whether the user's input is an actionable research topic or conversational chatter.
    If conversational (e.g. 'Hi'), asks the user to clarify/specify their research topic.
    If actionable, decomposes the topic into targeted web search queries.
    """
    topic = state["topic"]
    logger.info("PlannerNode: evaluating prompt intent: '%s'", topic)

    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(ResearchTopicEvaluation)

    system_prompt = (
        "You are DeepResearcher, an autonomous AI research assistant.\n\n"
        "First, evaluate the user's input:\n"
        "- If the user says 'hi', 'hello', asks 'who are you', or enters a conversational greeting/ambiguous fragment:\n"
        "  Set is_valid_topic=False and write a warm, helpful clarification message in Markdown explaining that you are an autonomous "
        "research agent, and inviting them to provide a specific question or topic they would like to investigate (give 2-3 concrete examples).\n"
        "- If the input is a valid topic, technical trade-off, or research inquiry:\n"
        "  Set is_valid_topic=True and generate 3 to 4 natural, high-signal web search queries covering different technical angles."
    )

    evaluation: ResearchTopicEvaluation = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User Input: {topic}"),
    ])

    if not evaluation.is_valid_topic:
        logger.info("Prompt '%s' identified as conversational/ambiguous. Requesting clarification.", topic)
        return {
            "needs_clarification": True,
            "final_report": evaluation.clarification_message,
            "status_message": "Awaiting clarified research topic.",
            "plan_queries": [],
            "search_queries": [],
        }

    queries = [q.strip() for q in evaluation.search_queries if q.strip()]
    if not queries:
        queries = [topic]

    logger.info("PlannerNode generated %d queries for topic '%s': %s", len(queries), topic, queries)

    return {
        "needs_clarification": False,
        "plan_queries": queries,
        "search_queries": queries,
        "iteration": 1,
        "max_iterations": state.get("max_iterations", 2),
        "status_message": f"Planned {len(queries)} targeted search queries.",
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
    Evaluates accumulated sources against the research topic.
    Identifies if critical dimensions are missing and generates natural follow-up queries.
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
        "If critical gaps exist, formulate 1 to 2 targeted follow-up search queries. If evidence is sufficient, set has_gaps=False."
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

    follow_up_queries = [fq.strip() for fq in decision.follow_up_queries if fq.strip()]

    if decision.has_gaps and follow_up_queries:
        logger.info("CriticNode: gaps identified. Formulated %d targeted queries for iteration %d: %s", len(follow_up_queries), iteration + 1, follow_up_queries)
        return {
            "gaps_found": True,
            "critique": decision.critique,
            "search_queries": follow_up_queries,
            "iteration": iteration + 1,
            "status_message": f"Identified knowledge gaps: {decision.critique[:90]}...",
        }
    else:
        logger.info("CriticNode: evidence sufficient. Moving to synthesis.")
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
