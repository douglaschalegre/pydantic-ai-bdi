# Pydantic AI BDI Framework

A sophisticated **BDI (Belief-Desire-Intention) agent framework** built on top of Pydantic AI. BDI is a cognitive architecture for intelligent agents that models how agents reason about their environment and make decisions.

## Overview

This project implements a BDI architecture that extends Pydantic AI's `Agent` class with the classic BDI cognitive model. The framework provides structured reasoning, adaptive planning, and human collaboration capabilities for building autonomous agents that can handle complex, multi-step tasks.

## Core Components

### BDI Agent (`bdi.py`)
The main `BDI` class extends Pydantic AI's `Agent` class and implements the classic BDI architecture:
- **Beliefs**: Information the agent holds about the world (managed by `BeliefSet`)
- **Desires**: High-level goals the agent wants to achieve  
- **Intentions**: Concrete plans of action (sequences of steps) to fulfill desires

### Data Schemas (`schemas.py`)
Defines the core data structures using Pydantic models:
- `Belief`: Represents facts the agent knows (with certainty, source, timestamp)
- `Desire`: High-level goals with priority and status tracking
- `Intention`: Structured plans containing sequential `IntentionStep` objects
- `IntentionStep`: Individual actionable steps that can be either tool calls or descriptive tasks

## Key Features

### 1. Two-Stage Planning
The agent uses a sophisticated planning approach:
- **Stage 1**: Converts desires into high-level intentions using LLM reasoning
- **Stage 2**: Breaks down each high-level intention into detailed, executable steps

### 2. Human-in-the-Loop (HITL)
When a step fails, the agent can:
- Present the failure context to a human user
- Accept natural language guidance from the user
- Use an LLM to interpret the guidance into structured plan modifications
- Apply various manipulation types (retry, modify, replace, skip, abort, etc.)

### 3. Plan Reconsideration
After each step execution, the agent evaluates whether the remaining plan is still valid based on:
- Current beliefs
- Step execution history
- Changed circumstances

### 4. MCP Server Integration
The agent integrates with MCP (Model Context Protocol) servers to access external tools, enabling connection to various external capabilities.

## BDI Reasoning Cycle

The agent runs a continuous reasoning cycle:

1. **Belief Update**: Update beliefs based on action outcomes
2. **Deliberation**: Check desire statuses and priorities
3. **Intention Generation**: Create new plans if needed using two-stage LLM planning
4. **Intention Execution**: Execute one step of the current plan
5. **Reconsideration**: Evaluate if the plan should continue or be modified

## Architecture Benefits

This implementation provides:

- **Structured reasoning**: Clear separation of beliefs, desires, and intentions
- **Adaptive planning**: Can reconsider and modify plans based on outcomes
- **Human collaboration**: Allows human intervention when automated planning fails
- **Tool integration**: Seamless connection to external capabilities via MCP
- **Explainable AI**: Verbose logging makes the agent's reasoning transparent
- **Type safety**: Built on Pydantic for robust data validation

## Human-in-the-Loop Features

When enabled, the HITL system provides:
- **Failure Analysis**: Detailed context about why a step failed
- **Natural Language Guidance**: Users can provide instructions in plain English
- **LLM Interpretation**: Automatic translation of user guidance into structured actions
- **Plan Manipulation**: Various ways to modify the current plan:
  - Retry current step as-is
  - Modify current step parameters
  - Replace current step with new ones
  - Insert new steps before/after current
  - Skip current step
  - Abort entire intention
  - Update beliefs and retry

## Applications

The BDI framework is suitable for:

- **Research assistants**: Conducting multi-step research tasks
- **Data analysis**: Complex analytical workflows
- **Content generation**: Multi-stage content creation pipelines
- **System automation**: Adaptive automation that can handle failures
- **Decision support**: Structured decision-making processes

## Requirements

- Python 3.10+
- An LLM API key or ollama server

## Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or: pip install uv

# Install dependencies
uv sync
```

## Usage Example

```python
# example.py
import asyncio
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.ollama import OllamaModel
from bdi import BDI

# Create an MCP server for git
git_server = MCPServerStdio(
    "uvx", args=["mcp-server-git"], tool_prefix="git", timeout=60
)

# Create a BDI agent
agent = BDI(
    model=OllamaModel("gemma3:1b", provider=OllamaProvider(base_url=os.getenv("OLLAMA_BASE_URL"))),
    desires=[
        "I need a report of the commit history of the pydantic-ai repository"
    ],
    intentions=[
        "Check the commit history of the pydantic-ai repository",
        "Summarize the commit history",
        "Create a presentation of the commit history"
    ],
    verbose=True,
    enable_human_in_the_loop=True,
    mcp_servers=[git_server]  # External tool integration
)

async def main():
    async with agent.run_mcp_servers():
        for i in range(5):
            print(f"\n===== Cycle {i + 1} =====")
            await agent.bdi_cycle()
            await asyncio.sleep(2)

asyncio.run(main())
```
## Running the example

```bash
uv run python example.py
```

## Running the dev server

```bash
uv run uvicorn server.app:app --reload --port 8000
```

## License

This project is open source and available under the MIT license.
