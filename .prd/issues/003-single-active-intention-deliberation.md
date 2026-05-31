---
title: Single Active Intention Deliberation
labels:
  - completed
type: AFK
status: completed
---

## What to build

Change deliberation so the agent adopts exactly one active Intention at a time. When no active Intention exists, planning should select one pending Desire and produce one committed Intention with one Plan. While an Intention is active, other pending Desires should wait and should not receive speculative Plans.

## Acceptance criteria

- [ ] Planning output selects one Desire and returns one committed Intention with one Plan.
- [ ] The cycle does not deliberate over pending Desires while an active Intention exists.
- [ ] Pending Desires remain pending until the active Intention reaches a terminal outcome.
- [ ] Planning does not produce speculative Plans for unselected Desires.
- [ ] Tests cover multiple pending Desires, one selected Intention, and no replanning while an Intention is active.

## Blocked by

- .prd/issues/002-plan-backed-intention-execution.md
