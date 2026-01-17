# BDI Framework Experiments

## Overview

Implement your BDI (Belief-Desire-Intention) agent here.

## Getting Started

1. Copy the template:
   ```bash
   cp TEMPLATE.py experiment-N.py  # Replace N with your participant number
   ```

2. Edit `experiment-N.py` and implement the `run_task()` method

3. Test your implementation:
   ```bash
   python experiment-N.py
   ```

## What to Implement

Focus on the BDI reasoning cycle:
- **Beliefs**: What knowledge should your agent extract and track?
- **Desires**: How do you represent goals?
- **Intentions**: How do you generate and execute plans?
- **Reconsideration**: When should plans be adapted?

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
