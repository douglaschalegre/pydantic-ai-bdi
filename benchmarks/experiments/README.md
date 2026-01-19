# Experiment Participant Guide

This directory contains templates and submission structure for multi-participant benchmark experiments.

## Overview

This study evaluates three agent frameworks:
- **BDI** (Belief-Desire-Intention)
- **LangGraph** (State machine graphs)
- **CrewAI** (Multi-agent collaboration)

### Important Distinction

- **BDI**: You **USE** the existing BDI agent (already implemented in `bdi/agent.py`). Just configure it for each task.

- **LangGraph & CrewAI**: You **IMPLEMENT** your own agent from scratch using these frameworks.

This compares the **BDI architecture as designed** against what you can build with other frameworks.

Each participant will work with all three frameworks to solve the same benchmark tasks.

## Directory Structure

```
experiments/
├── README.md           # This file
├── bdi/
│   ├── TEMPLATE.py    # BDI implementation template
│   ├── experiment-1.py
│   ├── experiment-2.py
│   └── ...
├── langgraph/
│   ├── TEMPLATE.py    # LangGraph implementation template
│   ├── experiment-1.py
│   ├── experiment-2.py
│   └── ...
└── crewai/
    ├── TEMPLATE.py    # CrewAI implementation template
    ├── experiment-1.py
    ├── experiment-2.py
    └── ...
```

## Getting Started

### 1. Setup Environment

#### What You Need

For running experiments, you need:
- **BDI Agent Framework** (pydantic-ai, etc.) - *Required to run BDI experiments*
- **Agent Frameworks** (LangGraph, CrewAI) - *Required to run comparison experiments*
- **Benchmark Tools** (scipy, numpy) - *Required for metrics collection*
- **Visualization** (matplotlib) - *Optional, for charts*

All of these are installed automatically with `benchmark-all`.

#### Using uv (Recommended - Fast!)

```bash
# Install uv (one time)
pip install uv

# Install everything from project root
cd pydantic-ai-bdi
uv sync --extra benchmark-all

# This installs:
# 1. BDI Agent Framework (bdi/, pydantic-ai)
# 2. LangGraph & CrewAI frameworks
# 3. Benchmark tools (scipy, numpy, psutil)
# 4. Visualization tools (matplotlib, seaborn)
```

See `INSTALLATION.md` for more options.

#### Verify Installation

```bash
# Check everything is installed
uv run python -c "import bdi; print('✓ BDI Framework')"
uv run python -c "import pydantic_ai; print('✓ Pydantic AI')"
uv run python -c "import langgraph; print('✓ LangGraph')"
uv run python -c "import crewai; print('✓ CrewAI')"
uv run python -c "import scipy; print('✓ SciPy')"
```

### 2. Get Your Participant Number

You will be assigned a participant number (e.g., 1, 2, 3...). Use this number for all your experiment files:
- `bdi/experiment-N.py`
- `langgraph/experiment-N.py`
- `crewai/experiment-N.py`

### 3. Implement Each Framework

For each framework, copy the TEMPLATE.py file and implement your agent:

```bash
# Example for participant 1
cp experiments/bdi/TEMPLATE.py experiments/bdi/experiment-1.py
cp experiments/langgraph/TEMPLATE.py experiments/langgraph/experiment-1.py
cp experiments/crewai/TEMPLATE.py experiments/crewai/experiment-1.py
```

Then edit each file to implement your solution.

## Implementation Guidelines

### What You Need to Implement

For each framework, you need to implement the `run_task()` method. This method receives:

**Input (task_definition):**
```python
{
    'id': 'simple_file_read',
    'goal': 'Read the pyproject.toml file and report the number of lines',
    'initial_context': {'file_path': 'pyproject.toml'},
    'tools_available': ['read_file', 'list_directory']
}
```

**Output (return value):**
```python
{
    'success': True,  # Whether the task succeeded
    'result': {...},  # Your result data
    'final_state': {...}  # Final agent state
}
```

### What's Provided (Boilerplate)

The templates provide:
- **Framework initialization** - Basic setup for each framework
- **Metric collection** - Automatic tracking of performance metrics
- **Task execution wrapper** - Standard interface for running tasks
- **Example structure** - Commented examples of how to use each framework

### What You Should Focus On

Design your agent's **reasoning and execution strategy**:
- How does your agent break down tasks?
- What's your planning approach?
- How do you handle failures?
- How do you track state/knowledge?
- What's your collaboration strategy (for multi-agent)?

### Tips for Each Framework

#### BDI Framework
- Focus on **belief extraction** - What knowledge is important?
- Define clear **desires** - What goals matter?
- Design **intention generation** - How do you plan?
- Consider **plan reconsideration** - When to adapt?

#### LangGraph
- Design your **state structure** - What needs to be tracked?
- Define **node functions** - What does each step do?
- Create **routing logic** - How to decide next steps?
- Consider **cycles** - When to loop back?

#### CrewAI
- Define **agent roles** - Who does what?
- Assign **clear responsibilities** - Avoid overlap
- Design **task dependencies** - What order matters?
- Consider **collaboration** - How do agents communicate?

## Testing Your Implementation

Each template can be run standalone for testing:

```bash
# Test your BDI implementation
uv run python benchmarks/experiments/bdi/experiment-N.py

# Test your LangGraph implementation
uv run python benchmarks/experiments/langgraph/experiment-N.py

# Test your CrewAI implementation
uv run python benchmarks/experiments/crewai/experiment-N.py
```

This will run a simple test task and show metrics.

## Running Official Benchmarks

Once your implementations are ready, run the official benchmark:

```bash
# Run all frameworks for participant N
uv run python -m benchmarks.experiments.run_experiments --participant N

# Run specific framework only
uv run python -m benchmarks.experiments.run_experiments --participant N --framework bdi

# Run specific task category
uv run python -m benchmarks.experiments.run_experiments --participant N --framework bdi --category simple
```

This will:
1. Run all 6 benchmark tasks (2 simple, 2 medium, 2 complex)
2. Collect performance metrics automatically
3. Generate results in `benchmarks/results/participant-N_{timestamp}/`
4. Save individual task results and summary statistics to JSON files

## What We Measure

### Performance Metrics (Automatic)
- Execution time
- Number of steps
- Number of retries
- LLM token usage
- API call count

### Quality Metrics (Automatic)
- Task success rate
- Correctness of results
- Completeness

### Code Metrics (Automatic)
- Lines of code in your implementation
- Function count
- Complexity score

### Usability Metrics (Survey)
After implementation, you'll complete a survey about:
- Setup difficulty
- Concept clarity
- Debugging ease
- Documentation quality
- Learning curve

## Rules and Guidelines

### DO:
✅ Implement all three frameworks (BDI, LangGraph, CrewAI)
✅ Use the provided boilerplate and templates
✅ Focus on agent design and reasoning logic
✅ Test your implementations before submission
✅ Ask questions if anything is unclear

### DON'T:
❌ Modify the benchmark tasks or validators
❌ Change the metric collection code
❌ Share your implementations with other participants
❌ Use external libraries beyond those provided
❌ Hardcode solutions for specific tasks

## Time Expectations

Per framework:
- **Learning**: 2-4 hours (reading docs, understanding framework)
- **Implementation**: 3-5 hours (designing and coding your agent)
- **Testing**: 1-2 hours (debugging, testing)
- **Total per framework**: ~6-11 hours

Total study time: ~18-33 hours for all three frameworks

## Getting Help

### Documentation
- See `BENCHMARKING.md` for overall framework docs
- See `benchmarks/USAGE_GUIDE.md` for detailed usage
- Read the template files carefully - they have extensive comments

### Common Issues
- **Import errors**: Make sure you're running from project root
- **Missing dependencies**: Run `pip install -r benchmarks/requirements.txt`
- **Framework not found**: Install framework-specific dependencies
- **API errors**: Check your OpenAI API key is set

### Questions
Contact the study coordinator with:
- Your participant number
- Framework you're working on
- Specific issue/question

## Submission

When complete, ensure you have:
- [ ] Implemented all three frameworks (experiment-N.py in each directory)
- [ ] Tested each implementation
- [ ] Run official benchmarks
- [ ] Completed the post-study survey
- [ ] No modifications to benchmark infrastructure

Your submissions should be:
- `experiments/bdi/experiment-N.py`
- `experiments/langgraph/experiment-N.py`
- `experiments/crewai/experiment-N.py`

Results will be automatically collected from `benchmarks/results/participant-N/`

## Example Workflow

1. **Day 1-2**: Learn BDI framework, implement experiment-N.py
2. **Day 3-4**: Learn LangGraph, implement experiment-N.py
3. **Day 5-6**: Learn CrewAI, implement experiment-N.py
4. **Day 7**: Run all benchmarks, review results, complete survey

## Ethics and Academic Integrity

This is a research study. Please:
- Work independently
- Do not share implementations
- Report any issues honestly
- Follow the guidelines
- Complete the study seriously

Your data will be anonymized and used only for research purposes.

## Good Luck!

Focus on designing creative and effective agents. There's no "right" answer - we want to see different approaches and learn what works best for different task types.

Questions? Email the study coordinator.
