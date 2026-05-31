---
title: HITL Uses Plan Interface
labels:
  - needs-triage
type: AFK
status: completed
---

## What to build

Migrate human-in-the-loop plan manipulation so it targets the Plan Interface and Plan Steps instead of mutating Intention step fields directly. This keeps HITL compatible with the new BDI lifecycle while preserving the decision not to introduce active-Intention interruption policy.

## Acceptance criteria

- [x] HITL failure context describes the active Plan and current Plan Step.
- [x] HITL step modification updates Plan Steps through the Plan Interface.
- [x] HITL insert, replace, and truncate operations preserve Intention commitment semantics.
- [x] HITL guidance can update Beliefs without requiring an Intention lifecycle reset.
- [x] Tests cover HITL plan manipulation using Plan and Plan Step concepts.

## Blocked by

- .prd/issues/002-plan-backed-intention-execution.md
- .prd/issues/005-plan-repair-preserves-commitment.md
