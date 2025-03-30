# Pydantic AI BDI Framework

A Belief-Desire-Intention (BDI) agent framework built on top of the Pydantic AI library.

## Overview

This project implements a BDI architecture for intelligent agents by extending the Pydantic AI Agent class. The BDI model is a popular approach in artificial intelligence for modeling rational agents, originally developed by Michael Bratman and implemented in various agent programming languages.

## Core Concepts

### BDI Architecture

The BDI (Belief-Desire-Intention) model structures intelligent agents around three key mental attitudes:

- **Beliefs**: The agent's knowledge about the world, which may be incomplete or incorrect.
- **Desires**: Goals the agent would like to achieve.
- **Intentions**: Commitments to action plans that the agent has decided to pursue.

### Reasoning Cycle

The BDI agent executes a continuous reasoning cycle:

1. **Perception**: Update beliefs based on new information
   - Automatic perception from registered perception tools 
   - Manual perception from external sources (optional)
2. **Deliberation**: Generate desires based on current beliefs
3. **Means-End Reasoning**: Form intentions (concrete action plans) to achieve desires
4. **Action**: Execute intentions

## Features

- **Type-Safe Agents**: Built on Pydantic for robust data validation and type safety
- **Modular Components**: Customizable perception handlers, desire generators, and intention selectors
- **Decorator-Based API**: Simple decorator-based API for registering components
- **Tool Integration**: Seamless integration with Pydantic AI's tool system
- **Phase-Specific Tools**: Tools can be registered for specific phases of the BDI cycle
- **Automatic Perception**: BDI cycles automatically gather perceptions from all registered perception tools

### Tools

Tools are registered with the `@agent.bdi_tool` decorator. They can be registered for specific phases of the BDI cycle.

- Perception phase: Tools that gather information from the environment to update beliefs
- Desire phase: Tools that help evaluate conditions when generating desires
- Intention phase: Tools that execute actions to fulfill intentions
- General phase: Tools available in all phases (default if no phase is specified)

## Example Usage

The framework allows for intuitive agent development:

```python
# Create a BDI agent
agent = BDI("openai:gpt-4")

# Register a perception handler to process tool data
@agent.perception_handler
async def temperature_handler(data, beliefs):
    if "temperature" in data:
        beliefs.add(Belief(name="room_temperature", value=data["temperature"]))

# Register a perception tool
@agent.bdi_tool(phases=["perception"])
async def fetch_temperature(ctx):
    temp = ctx.deps.get_current_temperature()
    return {"temperature": temp}

@agent.desire_generator
async def temp_desire_generator(beliefs):
    temp = beliefs.get("room_temperature").value
    if temp < 20:
        return [Desire(id="warm_up", priority=0.8)]
    return []

@agent.intention_selector
async def temp_intention_selector(desires, beliefs):
    for desire in desires:
        if desire.id == "warm_up":
            return [Intention(
                desire_id=desire.id,
                steps=[
                    IntentionStep(
                        description="Turn up heating",
                        tool_name="adjust_temperature",
                        tool_params={"target": 22.0}
                    )
                ]
            )]
    return []

# Define action tools
@agent.bdi_tool(phases=["intention"])
async def adjust_temperature(ctx, target):
    # Implement temperature adjustment logic
    return {"success": True}

# Run the BDI cycle with automatic perception
await agent.bdi_cycle()
```

## Applications

The BDI framework is suitable for a wide range of applications:

- Smart home automation
- Autonomous robots
- Personal assistants
- Multi-agent systems
- Decision support systems
- Game AI

## Requirements

- Python 3.9+
- Pydantic AI library

## License

This project is open source and available under the MIT license.
