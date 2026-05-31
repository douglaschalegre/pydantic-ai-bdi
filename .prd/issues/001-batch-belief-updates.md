---
title: Batch Belief Updates
labels:
  - completed
type: AFK
status: completed
---

## What to build

Build a batch belief update path that processes beliefs from a step outcome once, deduplicates repeated facts, deterministically upserts exact normalized belief names, and only uses ambiguity resolution when the incoming beliefs genuinely conflict with existing belief state. Failed-step retry handling should reuse the same extracted beliefs instead of triggering a second extraction pass.

## Acceptance criteria

- [ ] Step outcome analysis extracts beliefs once and makes those extracted beliefs available to retry handling.
- [ ] Duplicate extracted beliefs are removed before belief update evaluation.
- [ ] Exact normalized belief names are upserted deterministically without LLM name resolution.
- [ ] Ambiguous belief names or conflicting values are resolved through a batch path rather than one LLM call per belief.
- [ ] Belief update tests cover deterministic upsert, deduplication, ambiguity handling, and failed-step retry reuse.

## Blocked by

None - can start immediately
