# Experiment Participant Guide

This directory contains templates and submission structure for multi-participant benchmark experiments.

## Overview

This study evaluates three agent frameworks:
- **BDI** (Belief-Desire-Intention)
- **LangGraph** (State machine graphs)
- **CrewAI** (Multi-agent collaboration)

Each participant will implement agents in **all three frameworks** to solve the same benchmark tasks.

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

#### Using uv (Recommended - Fast!)

```bash
# Install uv
pip install uv

# Install from project root
cd pydantic-ai-bdi
uv pip install -e ".[benchmark-all]"
```

#### Using pip

```bash
# From project root
cd pydantic-ai-bdi
pip install -e ".[benchmark-all]"

# Or from benchmarks/ directory
cd benchmarks/
./install-benchmarks.sh
```

See `INSTALLATION.md` for more options.

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
python experiments/bdi/experiment-N.py

# Test your LangGraph implementation
python experiments/langgraph/experiment-N.py

# Test your CrewAI implementation
python experiments/crewai/experiment-N.py
```

This will run a simple test task and show metrics.

## Running Official Benchmarks

Once your implementations are ready, run the official benchmark:

```bash
# Run all your experiments
python -m benchmarks.experiments.run_experiments --participant N

# Or run specific framework
python -m benchmarks.experiments.run_experiments --participant N --framework bdi
```

This will:
1. Run all 24 benchmark tasks (simple, medium, complex)
2. Collect performance metrics automatically
3. Generate results in `benchmarks/results/participant-N/`
4. Create analysis reports

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
