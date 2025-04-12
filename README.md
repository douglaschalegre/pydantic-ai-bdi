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
2. **Deliberation**: Generate desires based on current beliefs (Currently implicit; could be formalized with desire generators)
3. **Intention Generation (Two-Stage)**: Form intentions (concrete action plans) based on desires, beliefs, and optional user guidance.
   - **Stage 1 (What)**: Generate high-level intentions based on desires, current beliefs, available tools, and any initial user guidance. Focuses on *what* needs to be done.
   - **Stage 2 (How)**: For each high-level intention, generate a detailed, step-by-step action plan using current beliefs and available tools. Focuses on *how* to achieve the goal.
4. **Action**: Execute the steps of the current intention.

## Features

- **Type-Safe Agents**: Built on Pydantic for robust data validation and type safety
- **Modular Components**: Customizable perception handlers
- **Decorator-Based API**: Simple decorator-based API for registering components like perception handlers and tools
- **Two-Stage Intention Generation**: Separates the planning process into identifying *what* needs to be done (high-level intentions) and *how* to do it (detailed steps), using LLM calls for potentially deeper reasoning.
- **Initial Intention Guidance**: Allows users to provide high-level strategic guidance during agent initialization, influencing the planning process without rigidly defining the final intentions.
- **Tool Integration**: Seamless integration with Pydantic AI's tool system
- **Phase-Specific Tools**: Tools can be registered for specific phases of the BDI cycle (perception, intention, etc.)
- **Automatic Perception**: BDI cycles automatically gather perceptions from all registered perception tools

### Tools

Tools are registered with the `@agent.bdi_tool` decorator. They can be registered for specific phases of the BDI cycle.

- Perception phase: Tools that gather information from the environment to update beliefs
- Desire phase: Tools that help evaluate conditions when generating desires
- Intention phase: Tools that execute actions to fulfill intentions
- General phase: Tools available in all phases (default if no phase is specified)

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
