"""
LangGraph State Schema for DeepResearcher
Defines the state structure that flows through each graph node.
"""
import operator
from typing import Annotated, TypedDict


class SourceItem(TypedDict):
    title: str
    url: str
    snippet: str


class ResearchState(TypedDict):
    # User's research topic or prompt
    topic: str

    # Queries generated in initial planning
    plan_queries: list[str]

    # Active queries executed in the current search pass
    search_queries: list[str]

    # Accumulated sources across iterations using operator.add reducer
    sources: Annotated[list[SourceItem], operator.add]

    # Critic reflection and gap detection
    critique: str
    gaps_found: bool

    # Iteration tracking & guardrail
    iteration: int
    max_iterations: int

    # Final synthesized Markdown report or clarification message
    final_report: str

    # Intent flag: True if the user prompt was conversational/ambiguous and needs clarification
    needs_clarification: bool

    # Status message streamed to client/terminal
    status_message: str
