# LangGraph Framework Experiments

## Overview

Implement your LangGraph state machine agent here.

## Getting Started

1. Install dependencies:
   ```bash
   pip install langgraph langchain-openai langchain-core
   ```

2. Copy the template:
   ```bash
   cp TEMPLATE.py experiment-N.py  # Replace N with your participant number
   ```

3. Edit `experiment-N.py` and implement your state machine

4. Test your implementation:
   ```bash
   python experiment-N.py
   ```

## What to Implement

Design your state machine:
- **State Structure**: What information needs to be tracked?
- **Nodes**: What processing happens at each step?
- **Edges**: How do you transition between states?
- **Routing**: When to take different paths?

## LangGraph Architecture

```
         ┌──────┐
    ┌───►│ Plan │───┐
    │    └──────┘   │
    │               ↓
┌───────┐      ┌─────────┐
│Review │◄─────│ Execute │
└───────┘      └─────────┘
    │               │
    └───────────────┘
     (conditional)
```

## Key LangGraph Concepts

- **StateGraph**: Defines your state machine
- **Nodes**: Functions that process and update state
- **Edges**: Connections between nodes
- **Conditional Edges**: Dynamic routing based on state
- **Checkpointing**: Save/restore state (optional)

## Tips

- Design your state schema first
- Keep nodes focused (single responsibility)
- Use conditional edges for decision points
- Consider cycles for iteration/retry logic
- Test your graph structure before adding complexity

## Resources

- [LangGraph Docs](https://python.langchain.com/docs/langgraph)
- See TEMPLATE.py for example structure
- Check `experiments/README.md` for guidelines
