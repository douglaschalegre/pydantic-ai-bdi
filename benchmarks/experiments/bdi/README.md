# BDI Framework Experiments

## Overview

**IMPORTANT**: For BDI experiments, you **USE** the existing BDI agent - you don't implement it from scratch!

The BDI agent is already implemented in `bdi/agent.py`. Your job is to:
1. Configure it appropriately for each task
2. Optionally provide initial desires/intentions
3. Let the BDI cycle run automatically

This evaluates the **BDI architecture as designed** against other frameworks.

## Getting Started

1. Copy the template:
   ```bash
   cp TEMPLATE.py experiment-N.py  # Replace N with your participant number
   ```

2. Edit `experiment-N.py` and configure the BDI agent in `run_task()`

3. Test your configuration:
   ```bash
   python experiment-N.py
   ```

## What You Configure

The BDI agent handles all reasoning automatically. You configure:
- **Model selection**: Which LLM to use (gpt-4, gpt-3.5-turbo, etc.)
- **Initial desires**: Starting goals (or use task goal)
- **Initial intentions**: Optional starting plan steps
- **Tools**: What functions the agent can call
- **Settings**: Verbose output, human-in-the-loop, logging

## BDI Architecture

```
┌─────────────┐
│   Beliefs   │ ← Knowledge about the world
└──────┬──────┘
       ↓
┌─────────────┐
│   Desires   │ ← Goals to achieve
└──────┬──────┘
       ↓
┌─────────────┐
│ Intentions  │ ← Plans to execute
└──────┬──────┘
       ↓
┌─────────────┐
│  Execution  │ ← Execute steps
└──────┬──────┘
       ↓
   (repeat cycle)
```

## Key BDI Concepts

- **Belief Revision**: Update knowledge based on observations
- **Deliberation**: Choose which desires to pursue
- **Means-End Reasoning**: Generate plans for desires
- **Plan Execution**: Execute intention steps
- **Plan Monitoring**: Check if plans are still valid

## Tips

- Start simple - get one task working first
- Use beliefs to avoid repeating work
- Consider when to reconsider plans
- Think about how to handle failures

## Resources

- See `bdi/` directory for framework code
- Read `BENCHMARKING.md` for overall study info
- Check `experiments/README.md` for guidelines
