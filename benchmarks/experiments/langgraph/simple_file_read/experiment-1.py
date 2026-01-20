"""LangGraph participant experiment for simple_file_read."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, TypedDict

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from langgraph.graph import StateGraph, END

from benchmarks.experiments.langgraph import runner


class AgentState(TypedDict):
    goal: str
    steps: int
    completed: bool


def build_agent(model):
    def plan(state: AgentState) -> AgentState:
        state["steps"] += 1
        return state

    def evaluate(state: AgentState) -> AgentState:
        state["completed"] = state["steps"] >= 1
        return state

    def should_continue(state: AgentState) -> str:
        return "end" if state["completed"] else "continue"

    workflow = StateGraph(AgentState)
    workflow.add_node("plan", plan)
    workflow.add_node("evaluate", evaluate)
    workflow.add_edge("plan", "evaluate")
    workflow.add_conditional_edges(
        "evaluate",
        should_continue,
        {"continue": "plan", "end": END},
    )
    workflow.set_entry_point("plan")
    return workflow.compile()


def run_agent(agent, metric_collector) -> Dict:
    initial_state: AgentState = {
        "goal": "Read the pyproject.toml file and report the number of lines.",
        "steps": 0,
        "completed": False,
    }
    result = agent.invoke(initial_state)
    metric_collector.record_step(success=True)
    return {"success": True, "result": result}


if __name__ == "__main__":
    runner.main(__file__)
