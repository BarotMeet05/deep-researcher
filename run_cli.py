"""
CLI Test Runner for DeepResearcher
Executes the LangGraph agent directly from the command line with live node streaming.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

import logging
from dotenv import load_dotenv

# Load .env from root
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from app.agent.graph import research_agent


def run_research(topic: str, max_iterations: int = 2):
    print("=" * 70)
    print(f"DEEPRESEARCHER AGENT: Starting Research on:\n'{topic}'")
    print(f"Max Reflection Loops: {max_iterations}")
    print("=" * 70)

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
        "status_message": "Initializing research...",
    }

    # Stream graph node execution step-by-step
    for event in research_agent.stream(initial_state):
        for node_name, node_output in event.items():
            print(f"\n[NODE COMPLETED: {node_name.upper()}]")
            if "status_message" in node_output:
                print(f"  Status: {node_output['status_message']}")

            if node_name == "planner":
                print(f"  Plan Queries: {node_output.get('plan_queries')}")

            elif node_name == "searcher":
                print(f"  Accumulated Sources: {len(node_output.get('sources', []))} new sources found")

            elif node_name == "critic":
                print(f"  Critique: {node_output.get('critique')}")
                print(f"  Gaps Found: {node_output.get('gaps_found')}")
                if node_output.get("search_queries"):
                    print(f"  Refined Queries: {node_output.get('search_queries')}")

            elif node_name == "synthesizer":
                print("\n" + "=" * 70)
                print("FINAL SYNTHESIZED REPORT")
                print("=" * 70)
                print(node_output.get("final_report"))
                print("=" * 70)


if __name__ == "__main__":
    test_topic = (
        "Compare PostgreSQL vs SQLite for embedded and edge applications in 2026: "
        "strengths, trade-offs, and optimal use cases"
    )
    if len(sys.argv) > 1:
        test_topic = " ".join(sys.argv[1:])

    run_research(test_topic, max_iterations=2)
