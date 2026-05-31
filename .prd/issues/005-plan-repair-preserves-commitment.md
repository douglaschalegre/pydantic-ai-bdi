---
title: Plan Repair Preserves Commitment
labels:
  - completed
type: AFK
status: completed
---

## What to build

On Plan Step failure, repair or replace the current Plan while preserving the committed Intention. The Desire should only be marked failed when the committed goal is impossible or repair is exhausted, not merely because one Plan Step or one Plan attempt failed.

## Acceptance criteria

- [ ] Failed Plan Steps can trigger Plan repair without de-adopting the active Intention.
- [ ] Failed Plan Steps can trigger Plan replacement while preserving the active Intention.
- [ ] Useful completed Plan Step History and Beliefs remain available after Plan repair or replacement.
- [ ] Desire failure is reserved for impossible, exhausted, or explicitly failed committed goals.
- [ ] Tests verify that Plan failure and Desire failure are separate lifecycle outcomes.

## Blocked by

- .prd/issues/004-conservative-plan-reconsideration.md
