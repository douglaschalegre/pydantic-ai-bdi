"""CrewAI participant experiment for simple_file_read."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from crewai import Agent, Task, Crew, Process

from benchmarks.experiments.crewai import runner


def build_agent(model):
    planner = Agent(
        role="Planner",
        goal="Plan the work",
        backstory="You create clear action plans.",
        verbose=True,
        llm=model,
    )
    executor = Agent(
        role="Executor",
        goal="Execute the plan",
        backstory="You carry out steps reliably.",
        verbose=True,
        llm=model,
    )

    task = Task(
        description="Read the pyproject.toml file and report the number of lines.",
        agent=executor,
        expected_output="Line count summary",
    )

    return Crew(
        agents=[planner, executor],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )


def run_agent(crew, metric_collector):
    result = crew.kickoff()
    metric_collector.record_step(success=True)
    return {"success": True, "result": result}


if __name__ == "__main__":
    runner.main(__file__)
