"""
LangGraph Nodes for DeepResearcher
Defines the functional nodes: Planner, Searcher, Critic, and Synthesizer.

Key design:
- Planner: validates intent, classifies format_style (comparison / curriculum_guide /
  deep_dive / executive_brief / conversational), and generates targeted search queries.
- Synthesizer: picks the appropriate Markdown template based on format_style so that
  the output structure always matches the nature of the question.
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
        description=(
            "True if the input is a genuine topic, technical question, domain inquiry, "
            "or comparison that can be investigated. False if it is a greeting (e.g. 'hi', "
            "'hello'), conversational chatter, or too underspecified to research."
        )
    )
    clarification_message: str = Field(
        default="",
        description=(
            "If is_valid_topic is False, a polite, conversational response explaining what "
            "DeepResearcher is and prompting the user with 2-3 concrete example research inquiries."
        ),
    )
    format_style: str = Field(
        default="executive_brief",
        description=(
            "The most appropriate output structure for this topic. Choose exactly one of:\n"
            "  'comparison'       – User wants to compare two or more technologies, products, "
            "approaches, or frameworks (e.g. 'PostgreSQL vs SQLite', 'React vs Vue').\n"
            "  'curriculum_guide' – User wants a curated learning path, problem set, reading "
            "list, or ranked resource guide (e.g. 'best coding questions for graphs', "
            "'top 10 papers on transformers').\n"
            "  'deep_dive'        – User wants an in-depth technical explanation, architecture "
            "breakdown, or how-something-works analysis (e.g. 'how does RAFT consensus work', "
            "'explain transformer attention').\n"
            "  'executive_brief'  – User wants market intelligence, industry trends, business "
            "strategy, timelines, or high-level strategic outlook (e.g. 'state of EV batteries "
            "2026', 'commercial viability of solid-state batteries').\n"
            "Default to 'executive_brief' when unsure."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        description=(
            "If is_valid_topic is True, 3 to 4 natural, diverse web search queries exploring "
            "different aspects of the topic."
        ),
    )


class CritiqueDecision(BaseModel):
    has_gaps: bool = Field(
        description=(
            "True if critical aspects, data points, or viewpoints are missing from the gathered "
            "evidence. False if gathered info is sufficient."
        )
    )
    critique: str = Field(
        description=(
            "Detailed explanation of what information is present, what is missing, and whether "
            "additional searches are genuinely required."
        )
    )
    follow_up_queries: list[str] = Field(
        default_factory=list,
        description=(
            "Specific, targeted follow-up search queries to fill the identified gaps. "
            "Empty if has_gaps is False."
        ),
    )


# ---------------------------------------------------------------------------
# Synthesizer prompt templates — one per format_style
# ---------------------------------------------------------------------------

_PROMPT_COMPARISON = """\
You are a senior technical analyst. Write a rigorous, structured **comparison dossier** in Markdown.

EVIDENCE & QUALITY RULES:
1. RELEVANCE FILTERING: Discard completely off-topic sources (pop culture, unrelated products, etc.).
2. TECHNICAL DEPTH: Fill in known facts from your domain knowledge if live sources were sparse. \
Never leave table cells empty.
3. Add a brief note if live web evidence was partially unavailable.

REQUIRED OUTPUT STRUCTURE (use exactly these headings):
# Research Dossier: <Descriptive Title>

## TL;DR — Verdict
One paragraph. When should you choose option A? When option B? Clear, opinionated recommendation.

## Side-by-Side Comparison

| Criterion | <Option A> | <Option B> |
|-----------|-----------|-----------|
| ... | ... | ... |

Fill at least 10 meaningful rows (performance, footprint, concurrency, licensing, ecosystem, etc.)

## Deep-Dive Analysis
### <Option A>
### <Option B>
### Trade-offs & Edge Cases

## Decision Framework
Bullet list of "Choose A if…" / "Choose B if…" scenarios.

## Sources & References
- [Title](URL) for every cited source.
"""

_PROMPT_CURRICULUM = """\
You are an expert educator and senior software engineer. Write a **curated learning curriculum** \
in Markdown — structured like a high-quality syllabus or roadmap, NOT a corporate executive brief.

EVIDENCE & QUALITY RULES:
1. RELEVANCE FILTERING: Discard off-topic noise.
2. COMPLETENESS: Use your deep technical knowledge to fill gaps the web search may have missed.
3. For coding problems, include the problem name, platform (e.g. LeetCode), difficulty, the core \
concept/pattern it teaches, and a brief note on the key insight or common mistake.

REQUIRED OUTPUT STRUCTURE (use exactly these headings):
# <Topic> — Learning Roadmap & Curated Problem Set

## Overview & Why This Matters
2-3 sentences on why mastering this topic is valuable.

## Core Concepts & Prerequisites
Bullet list of concepts learners must understand first.

## Curated Problem Set / Resource List

Organise by theme or difficulty tier (Easy → Medium → Hard or by conceptual category). \
For each item:

### <Category or Tier Name>

| # | Problem / Resource | Platform | Difficulty | Core Pattern / What You Learn | Key Insight |
|---|--------------------|----------|------------|-------------------------------|-------------|
| 1 | ... | ... | ... | ... | ... |

## Algorithmic Patterns & Code Templates
For each major pattern mentioned, include a brief Python/pseudocode template with inline comments.

## Common Mistakes & How to Avoid Them
Bullet list of traps learners fall into and the counter-strategy.

## Practice Strategy & Timeline
How many problems per day, in what order, over how many weeks.

## Sources & References
- [Title](URL)
"""

_PROMPT_DEEP_DIVE = """\
You are a principal engineer and technical writer. Write a **deep-dive technical explanation** \
in Markdown — thorough, precise, and practitioner-oriented.

EVIDENCE & QUALITY RULES:
1. RELEVANCE FILTERING: Discard off-topic sources entirely.
2. TECHNICAL COMPLETENESS: Draw on your domain knowledge freely when sources are sparse.
3. Use diagrams where helpful. Represent flow or architecture as Mermaid code blocks (```mermaid).
4. Include concrete code examples where relevant (use appropriate language fences).

REQUIRED OUTPUT STRUCTURE (use exactly these headings):
# Deep Dive: <Descriptive Title>

## What Is It & Why Does It Matter
Brief motivation and context.

## Core Mechanics
Explain the internals step-by-step. Use subsections per component.

## Architecture / Flow Diagram
Include at least one Mermaid diagram (flowchart or sequenceDiagram):

```mermaid
flowchart TD
    A[...] --> B[...]
```

## Worked Example
Concrete walkthrough with code.

## Edge Cases, Failure Modes & Gotchas
What goes wrong and why.

## Performance Characteristics
Time & space complexity, benchmarks, or latency profiles.

## Real-World Usage & Ecosystem
Libraries, frameworks, production use-cases.

## Sources & References
- [Title](URL)
"""

_PROMPT_EXECUTIVE_BRIEF = """\
You are a senior research analyst producing an **executive intelligence brief** in Markdown — \
the kind delivered to a CTO, investor, or strategy team.

EVIDENCE & QUALITY RULES:
1. RELEVANCE FILTERING: Discard entirely off-topic sources.
2. COMPLETENESS: Supplement sparse web evidence with established industry knowledge.
3. NEVER leave table cells with "No data available". Use industry consensus or flag as estimate.

REQUIRED OUTPUT STRUCTURE (use exactly these headings):
# Research Dossier: <Descriptive Title>

## Executive Summary
3-5 sentence high-level brief. Key takeaways, current state, and recommendation.

## Detailed Findings & Thematic Analysis
Grouped sub-sections covering major themes, technologies, players, timelines.

## Comparative Breakdown / Data Table
Markdown table with at least 8 meaningful rows.

## Strategic Implications & Future Outlook
Risks, opportunities, timeline milestones, what to watch.

## Sources & References
- [Title](URL)
"""

_FORMAT_PROMPTS: dict[str, str] = {
    "comparison": _PROMPT_COMPARISON,
    "curriculum_guide": _PROMPT_CURRICULUM,
    "deep_dive": _PROMPT_DEEP_DIVE,
    "executive_brief": _PROMPT_EXECUTIVE_BRIEF,
}


# ---------------------------------------------------------------------------
# Node 1: Planner & Intent Evaluator
# ---------------------------------------------------------------------------
def planner_node(state: ResearchState) -> dict:
    """
    Evaluates whether the user's input is an actionable research topic or conversational chatter.
    - Conversational/ambiguous input → returns a clarification message immediately.
    - Valid topic → generates targeted search queries AND classifies format_style so the
      Synthesizer can pick the most appropriate output structure.
    """
    topic = state["topic"]
    logger.info("PlannerNode: evaluating prompt intent: '%s'", topic)

    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(ResearchTopicEvaluation)

    system_prompt = (
        "You are DeepResearcher, an autonomous AI research assistant.\n\n"
        "Step 1 — Validate intent:\n"
        "  • If the user sends a greeting ('hi', 'hello'), asks who you are, or submits something "
        "too vague to research meaningfully: set is_valid_topic=False and write a warm Markdown "
        "clarification message inviting them to give a specific research topic (include 2-3 examples).\n"
        "  • Otherwise set is_valid_topic=True.\n\n"
        "Step 2 — If valid, classify the best output format:\n"
        "  • 'comparison'       → user is comparing two or more options (technologies, products, etc.)\n"
        "  • 'curriculum_guide' → user wants a learning path, problem set, resource list, or reading list\n"
        "  • 'deep_dive'        → user wants a detailed explanation of how something works\n"
        "  • 'executive_brief'  → user wants market/industry analysis, trends, strategic outlook\n\n"
        "Step 3 — Generate 3-4 precise, diverse web search queries covering the key angles."
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
            "format_style": "executive_brief",
            "status_message": "Awaiting clarified research topic.",
            "plan_queries": [],
            "search_queries": [],
        }

    queries = [q.strip() for q in evaluation.search_queries if q.strip()]
    if not queries:
        queries = [topic]

    format_style = evaluation.format_style or "executive_brief"
    if format_style not in _FORMAT_PROMPTS:
        format_style = "executive_brief"

    logger.info(
        "PlannerNode: topic='%s' | format_style='%s' | %d queries: %s",
        topic, format_style, len(queries), queries,
    )

    return {
        "needs_clarification": False,
        "plan_queries": queries,
        "search_queries": queries,
        "format_style": format_style,
        "iteration": 1,
        "max_iterations": state.get("max_iterations", 2),
        "status_message": f"Classified as '{format_style}'. Planned {len(queries)} targeted search queries.",
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
        logger.info(
            "CriticNode: gaps identified. Formulated %d targeted queries for iteration %d: %s",
            len(follow_up_queries), iteration + 1, follow_up_queries,
        )
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
            "critique": decision.critique if decision.has_gaps else "Information is comprehensive. Ready to synthesize.",
            "search_queries": [],
            "status_message": "Proceeding to synthesis.",
        }


# ---------------------------------------------------------------------------
# Node 4: Synthesizer — Adaptive format-aware report generation
# ---------------------------------------------------------------------------
def synthesizer_node(state: ResearchState) -> dict:
    """
    Synthesizes evidence into a Markdown report whose structure is determined by
    the format_style classified by the Planner:
      - comparison       → trade-off matrix & decision framework
      - curriculum_guide → learning roadmap, problem table, code templates
      - deep_dive        → mechanics, Mermaid diagrams, code examples
      - executive_brief  → classic executive dossier with strategic outlook
    """
    topic = state["topic"]
    sources = state.get("sources", [])
    format_style = state.get("format_style", "executive_brief")
    if format_style not in _FORMAT_PROMPTS:
        format_style = "executive_brief"

    logger.info(
        "SynthesizerNode: format_style='%s', generating report from %d sources",
        format_style, len(sources),
    )

    evidence_text = "\n\n".join(
        f"Source [{i+1}]: {s['title']}\nURL: {s['url']}\nSnippet: {s['snippet']}"
        for i, s in enumerate(sources)
    )

    system_prompt = _FORMAT_PROMPTS[format_style]

    user_msg = (
        f"Research Topic: {topic}\n\n"
        f"Gathered Evidence:\n{evidence_text or 'No direct web snippets available — use domain knowledge.'}\n\n"
        "Write the complete Markdown report now:"
    )

    llm = get_llm(temperature=0.1)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    logger.info("SynthesizerNode: report generated (%d characters)", len(response.content))
    return {
        "final_report": response.content,
        "status_message": f"Report synthesized ({format_style} format).",
    }
