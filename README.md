# Voluntas

Voluntas is a BDI (Belief-Desire-Intention) agent framework built on top of
[Pydantic AI](https://ai.pydantic.dev/). It provides structured beliefs,
desires, intentions, adaptive planning, execution, reconsideration, usage
tracking, and optional human-in-the-loop intervention.

## Installation

```bash
pip install voluntas
```

Or with uv:

```bash
uv add voluntas
```

The distribution name is `voluntas` and the Python import is also `voluntas`.

## Quick start

```python
import asyncio

from pydantic_ai.models.test import TestModel
from voluntas import BDI


async def main() -> None:
    agent = BDI(
        model=TestModel(),
        desires=["Prepare a concise project status report"],
        intentions=["Inspect the available project information"],
    )

    await agent.bdi_cycle()


asyncio.run(main())
```

For production use, replace `TestModel` with a model supported by Pydantic AI
and install any provider-specific dependencies required by that model.

## Public API

The main agent and commonly used schemas are available from the package root:

```python
from voluntas import (
    BDI,
    BDIUsageTracker,
    Belief,
    BeliefSet,
    Desire,
    DesireStatus,
    Intention,
    Plan,
)
```

The complete schema surface is available from `voluntas.schemas`:

```python
from voluntas.schemas import (
    BeliefExtractionResult,
    HighLevelIntentionList,
    PlanManipulationDirective,
    ReconsiderResult,
)
```

## BDI lifecycle

Each cycle coordinates the following stages:

1. Update beliefs from the current context and action outcomes.
2. Deliberate over pending desires and their priorities.
3. Generate a high-level intention when no active intention exists.
4. Execute one intention step using Pydantic AI tools and toolsets.
5. Reconsider the remaining plan after failed or changed work.

The framework supports MCP servers through the Pydantic AI integration passed
to `BDI`, as well as structured logs and aggregate usage tracking through
`BDIUsageTracker`.

## Human-in-the-loop

Set `enable_human_in_the_loop=True` to allow failures to be presented to a
human for guidance. The guidance is interpreted into structured actions such
as retrying, modifying, replacing, inserting, skipping, or aborting plan
steps.

## Development

Clone the repository and install development dependencies with uv:

```bash
uv sync --group dev
uv run pytest
```

The repository also contains SBench and benchmark runners for research and
experiments. The runners use a local LiteLLM proxy that exposes an
OpenAI-compatible API; they are development applications and are not part of
the published `voluntas` package.

Set the proxy connection before running the local examples:

```bash
export LITELLM_BASE_URL=http://localhost:4000
export LITELLM_API_KEY=sk-1234
export LITELLM_MODEL=gpt-5.3-codex
```

The value of `LITELLM_MODEL` must match a model alias configured in the proxy.

## Automated releases

Releases are selected by applying exactly one of these labels to a pull request
before it is merged into `main`:

- `release:patch` bumps `0.1.0` to `0.1.1`.
- `release:minor` bumps `0.1.0` to `0.2.0`.
- `release:major` bumps `0.1.0` to `1.0.0`.

After the merge, the release workflow updates the package version and lockfile,
runs lint and tests, builds and validates the distributions, creates a release
commit and tag, and publishes to PyPI. A merged pull request without a release
label does not publish anything. Multiple release labels make the workflow fail
instead of choosing a version implicitly.

One-time repository setup is required:

1. Create the three labels listed above.
2. Create a GitHub environment named `pypi`.
3. Add a PyPI Trusted Publisher for owner `douglaschalegre`, repository
   `voluntas`, workflow `release.yml`, and environment `pypi`.
4. Allow GitHub Actions to write repository contents, and ensure the `main`
   branch rules allow the workflow to push its release commit and tag.

The `pypi` environment can have required reviewers if publishing should wait
for a final approval. Without reviewers, publishing proceeds automatically
after the labeled pull request is merged.

## License

Voluntas is released under the MIT license.
