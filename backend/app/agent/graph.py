"""
LangGraph Assembly & Compilation
Wires StateGraph with nodes and conditional reflective edges.
"""
import logging
from langgraph.graph import StateGraph, START, END

from app.agent.state import ResearchState
from app.agent.nodes import planner_node, search_node, critic_node, synthesizer_node

logger = logging.getLogger(__name__)


def should_continue(state: ResearchState) -> str:
    """
    Conditional routing edge function.
    Decides whether to loop back to 'searcher' or proceed to 'synthesizer'.
    """
    gaps_found = state.get("gaps_found", False)
    queries = state.get("search_queries", [])
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 2)

    logger.info("Routing decision: gaps_found=%s, queries=%d, iter=%d/%d", gaps_found, len(queries), iteration, max_iterations)

    if gaps_found and queries and iteration <= max_iterations:
        logger.info("--> Looping back to 'searcher' for refined queries")
        return "searcher"

    logger.info("--> Proceeding to 'synthesizer'")
    return "synthesizer"


def build_research_graph():
    """
    Assembles and compiles the LangGraph research state machine.
    """
    workflow = StateGraph(ResearchState)

    # 1. Register Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("searcher", search_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # 2. Connect Edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "searcher")
    workflow.add_edge("searcher", "critic")

    # 3. Add Reflective Conditional Loop
    workflow.add_conditional_edges(
        "critic",
        should_continue,
        {
            "searcher": "searcher",
            "synthesizer": "synthesizer",
        },
    )

    workflow.add_edge("synthesizer", END)

    # 4. Compile into executable runnable
    app = workflow.compile()
    return app


# Module-level compiled graph singleton
research_agent = build_research_graph()
