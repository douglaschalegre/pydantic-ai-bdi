# BDI Agent Benchmarking Framework

## Overview

This benchmarking framework evaluates the Pydantic AI BDI (Belief-Desire-Intention) agent architecture and compares it with other agent frameworks for scientific research in software engineering.

## Research Questions

1. **Success Rate**: How reliably does the BDI agent complete tasks compared to other frameworks?
2. **Ease of Use**: How easy is it to define and execute tasks in BDI vs other frameworks?
3. **Task Complexity**: How does performance differ between simple vs long-running tasks?
4. **Resource Efficiency**: What are the costs (time, tokens, API calls) for task completion?

## Benchmark Task Taxonomy

### Task Categories

**Simple Tasks** (1-3 steps, <2 minutes expected)
- File operations (read, write, search)
- Basic data transformations
- Straightforward calculations

**Medium Tasks** (4-10 steps, 2-10 minutes expected)
- Multi-file analysis
- Data extraction and summarization

**Complex Tasks** (10+ steps, >10 minutes expected)
- Multi-component system integration
- Research and implementation tasks

## Metrics Collected

### Performance Metrics
- **Success Rate**: % of tasks completed successfully
- **Time to Completion**: Wall-clock time from start to finish
- **Cycle Count**: Number of reasoning cycles (BDI-specific)
- **Step Count**: Total steps executed
- **Retry Count**: Number of failed steps that required retry

### Quality Metrics
- **Plan Efficiency**: Ratio of necessary steps to total steps
- **Belief Accuracy**: % of correct beliefs extracted
- **Goal Achievement**: Completeness of task objectives

### Resource Metrics
- **Token Usage**: Total tokens consumed (input + output)
- **API Call Count**: Number of LLM API calls
- **Estimated Cost**: Based on model pricing

### Usability Metrics
- **Lines of Code**: Framework-specific code required
- **Cognitive Complexity**: Cyclomatic complexity of task definition
- **Human Interventions**: Number of HITL interactions required

## Frameworks Compared

This benchmark compares three major agent frameworks:

1. **Pydantic AI BDI** (this framework)
   - Belief-Desire-Intention architecture
   - Explicit reasoning with beliefs, desires, and intentions
   - Built-in plan reconsideration and human-in-the-loop support

2. **LangGraph** (state machine approach)
   - LangChain's graph-based agent framework
   - Explicit control flow with nodes and edges
   - Deterministic state transitions

3. **CrewAI** (multi-agent collaboration)
   - Role-based multi-agent system
   - Collaborative task execution
   - Agent specialization and parallel processing

## Directory Structure

```
benchmarks/
├── README.md                    # This file
├── tasks/                       # Task definitions
│   ├── simple/
│   ├── medium/
│   └── complex/
├── agents/                      # Agent implementations
│   ├── base_agent.py           # Base interface for all agents
│   ├── bdi_agent.py            # BDI implementation
│   ├── langgraph_agent.py      # LangGraph implementation
│   └── crewai_agent.py         # CrewAI implementation
├── metrics/                     # Metrics collection
│   └── collector.py            # Metrics collector
├── evaluation/                  # Evaluation framework
│   ├── runner.py               # Benchmark runner
│   └── validator.py            # Success validation
├── results/                     # Benchmark results (gitignored)
```

## Usage

Install dependencies from the repo root:

```bash
uv sync
```

### Running Participant Experiments

```bash
# Run all frameworks for a task
uv run python -m benchmarks.experiments.run_experiments --participant 1 --task-id simple_file_read

# Run a specific framework for a task
uv run python -m benchmarks.experiments.run_experiments --participant 1 --framework bdi --task-id simple_file_read
```

### Analyzing Results

Statistical analysis tooling is currently not included.

## Statistical Analysis

- **Success Rate Comparison**: Chi-square test for categorical success/failure
- **Time Performance**: ANOVA/Kruskal-Wallis for comparing multiple frameworks
- **Effect Size**: Cohen's d for practical significance
- **Confidence Intervals**: 95% CI for all metrics
- **Multiple Testing Correction**: Bonferroni correction where applicable

## Reproducibility

- All benchmark runs are logged with:
  - Git commit hash
  - Environment details (Python version, package versions)
  - Model specifications
  - Random seed (for reproducible LLM sampling)
  - Timestamp and duration

## License

Same as parent project (MIT)
