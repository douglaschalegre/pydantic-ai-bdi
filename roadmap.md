# BDI Agent Roadmap

This roadmap captures agreed directions focusing on accessibility for non-developers, long‑lived agent sessions, and natural language (NL) based configuration (no code exposed to end users initially).

## 1. Vision
Enable any user (no local install or coding) to spin up a persistent BDI agent that continuously pursues their stated goals, interacts via natural language, and leverages external capabilities (Git, summarization, etc.) while remaining transparent and steerable.

## 2. Core Principles
- NL → Configuration (no raw code surfaced to user in early phases)
- Long‑lived sessions (agent runs until explicitly stopped)
- Continuous deliberation cycles with observable progress
- Incremental complexity: start minimal, validate value early
- Human-in-the-loop (HITL) interaction via chat (replace terminal)
- Capability abstraction: users request outcomes, system maps to tools/MCP servers
- Persistence & resumability (later phase)

## 3. Deployment Modalities Considered
| Option | Description | User Friction | Ops Complexity | Notes |
|--------|-------------|---------------|----------------|-------|
| A: Hosted SaaS | Multi-tenant web app; users log in, create agents | Lowest | High (infra, scaling, billing) | Primary target for broad accessibility |
| B: Container + Web UI | Single docker run starts web + API locally | Medium (must have Docker) | Medium | Bridge for power users, can coexist |

> Difference A vs B: A is centrally hosted & managed (multi-user, shared infra). B is self-hosted (each user runs their own isolated instance via container). Scaling in A = horizontal workers + queue. Scaling in B = user’s machine resources.

(Desktop packaging and code export are intentionally deferred; guardrails deferred.)

## 4. High-Level Architecture
- Web Frontend: Agent creation form (NL Brief), live chat/log panel, status cards.
- API / Orchestrator Service: Validates brief → produces structured Agent Config JSON → launches agent runtime task.
- Agent Runtime Workers: Execute deliberation cycles; communicate events (cycle start/end, intention updates, tool actions) via event bus.
- Event Bus / Queue: (e.g., Redis streams, NATS, or RabbitMQ) decouples UI updates from runtime.
- State Store: Durable storage of agent config, beliefs snapshot, intentions, artifacts metadata.
- Capability Layer: Maps high-level requested capabilities to either:
  - Internal adapters
  - External MCP servers
  - Third-party tool platforms (smithery.ai, context7) — via unified wrapper.

## 5. Natural Language → Configuration Flow
1. User supplies Brief (single text field).
2. NL Extraction Prompt → returns JSON conforming to AgentConfig schema:
   ```jsonc
   {
     "desires": ["..."],
     "initial_intentions": ["..."],
     "constraints": ["optional"],
     "model": {"type": "gpt-4o", "temperature": 0.7},
     "mcp_servers": {
       "git": {"url": "http://...", "api_key": "optional"}
     },
   }
   ```
3. Validate (Pydantic / schema). Attempt auto-repair if invalid.
4. Present Preview to user → Confirm → Agent instance created.

## 6. Phased Roadmap
### Phase 0 – Idea Validation (Current)
- Terminal prototype (existing) proves deliberation loop & HITL failover.
- Collect user feedback on clarity of logs & outcome utility.

### Phase 1 – MVP NL Config + Single Agent
- Minimal web UI: Create Agent (Brief + Start), Live Log (read-only), Stop button.
- NL → Config extraction & validation.
- Single worker process (no horizontal scaling yet).
- Basic capability set (Git via existing MCP server).

### Phase 2 – Runtime Scaling & Multi-Agent
- Introduce job queue (e.g., Redis + RQ / Celery / custom asyncio scheduler).
- Multiple workers executing cycles concurrently (bounded concurrency per agent).
- Adaptive cycle pacing (backoff when idle, tighten when active intentions remain).
- Per-cycle persistence (beliefs snapshot + intention statuses).

### Phase 3 – Interactive HITL Chat
- Replace terminal intervention with web chat.
- Message Types: user_command, clarification_request, status_update, error_notice.
- NL Classification gateway: map user messages to actions (add desire, reprioritize, pause intention, inject fact/belief).
- Streaming of cycle decisions into chat timeline.

### Phase 4 – Capability Abstraction & External Tool Integrations
- Capability registry: maps capability key → provider strategy (internal adapter | MCP server | smithery.ai | context7).
- Dynamic capability resolution prior to intention execution.
- Monitoring of tool latency & failure; fallback ordering (e.g., smithery → local MCP → degrade gracefully).

### Phase 5 – Persistence, Resumption & Export
- Full state rehydration (resume agent after crash/redeploy).
- Periodic history summarization to shrink context.
- Optional “Export Config as Code” (generate Python scaffold for advanced users) – isolated advanced feature.

(Guardrails intentionally postponed until after viability proven.)

## 7. Scaling Strategy (Phase 2+)
- Each agent cycle enqueued as discrete job; enqueue next cycle upon completion.
- Cycle Job SLA: short-running (< model latency + tool IO).
- Horizontal scale: Add workers to consume cycle jobs; agent state fetched at start & persisted at end (optimistic locking via state version).
- Adaptive Cadence Algorithm:
  - If no pending unsatisfied intentions → exponentially increase wait (cap at max_seconds).
  - If new desire injected / intention unblocked → reset to min_seconds.
- Metrics for scale planning: avg cycle time, tool latency distribution, queue depth, active agent count.

## 8. MCP / Tool Capability Management (Smithery & Context7)
- Define abstract interface (CapabilityProvider) with methods: `prepare()`, `invoke(action, params)`, `health()`, `list_actions()`.
- Adapters:
  - MCPAdapter (wraps existing MCP server tools)
  - SmitheryAdapter (per smithery.ai docs)
  - Context7Adapter (for contextual retrieval / embeddings if exposed)
- Capability Registry JSON example:
  ```jsonc
  {
    "git_history": {"provider": "mcp", "server": "git", "tool": "git.list_commits"},
    "summarize": {"provider": "model", "strategy": "llm_summarize"},
    "embedding_search": {"provider": "context7", "index": "default"}
  }
  ```
- Resolution Flow during intention execution:
  1. Intention step declares needed capability (or inferred).
  2. Registry returns concrete invocation mapping.
  3. Provider adapter executes & returns structured result.

## 9. HITL Chat Interaction Model (Phase 3)
- WebSocket channel per agent.
- Event Types:
  - `cycle.started`
  - `cycle.completed`
  - `intention.updated`
  - `capability.invocation`
  - `error`
  - `summary`
- User Input Commands (natural language):
  - "Add goal ..." → append desire
  - "Pause intention X" → mark paused
  - "Focus on ..." → reprioritize desires
  - "Fact: <key>=<value>" → belief injection
  - "Status?" → force status summarization
- Classifier prompt ensures mapping to internal action schema; ambiguous inputs trigger clarification.

## 10. Deferred (Explicitly Not in Early Phases)
- Guardrails (budget limits, advanced safety policies)
- Multi-model routing
- Desktop packaging
- Extensive analytics dashboards

## 11. Open Questions (To Resolve Later)
- User API key handling vs platform-provided billing
- Data retention policy & privacy boundaries
- Max simultaneous agents per user
- Persistence backend choice (Postgres vs document store) – performance vs flexibility
- Observability stack (minimal logs vs full traces)

## 12. Immediate Next Practical Steps (Post-Roadmap)
1. Define `AgentConfig` Pydantic model with fields outlined in Section 5.
2. Implement NL → Config extraction function with validation & repair.
3. Wrap current terminal loop to accept injected config object.
4. Add serialization of cycle summaries to a JSON file (proto persistence).

---
This roadmap strictly reflects selections you highlighted: NL configuration (no early code exposure), hosted SaaS preference clarified vs container option, integration path for smithery/context7, HITL chat future replacement, and deferral of guardrails.
