# CrewAI Framework Experiments

## Overview

Implement your CrewAI multi-agent system here.

## Getting Started

1. Install dependencies:
   ```bash
   pip install crewai crewai-tools
   ```

2. Copy the template:
   ```bash
   cp TEMPLATE.py experiment-N.py  # Replace N with your participant number
   ```

3. Edit `experiment-N.py` and implement your multi-agent crew

4. Test your implementation:
   ```bash
   python experiment-N.py
   ```

## What to Implement

Design your agent team:
- **Roles**: What specializations do you need?
- **Goals**: What is each agent responsible for?
- **Tasks**: How do you decompose the work?
- **Collaboration**: How do agents work together?

## CrewAI Architecture

```
┌─────────────────┐
│  Planner Agent  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────────┐
│ Executor Agent  │ ←──→ │ Reviewer Agent   │
└─────────────────┘      └──────────────────┘
         │
         ↓
   Final Result
```

## Key CrewAI Concepts

- **Agent**: Individual AI entity with role and goal
- **Task**: Unit of work assigned to an agent
- **Crew**: Collection of agents working together
- **Process**: How agents collaborate (sequential/hierarchical)
- **Tools**: Capabilities agents can use

## Tips

- Define clear, non-overlapping roles
- Assign specific responsibilities to each agent
- Consider task dependencies
- Use sequential process for simple workflows
- Consider hierarchical for complex coordination
- Give agents tools they need for their role

## Resources

- [CrewAI Docs](https://docs.crewai.com/)
- See TEMPLATE.py for example structure
- Check `experiments/README.md` for guidelines
