from importlib.metadata import version as distribution_version

from pydantic_ai.models.test import TestModel

from voluntas import BDI, BDIUsageTracker, Belief, Desire, Intention, __version__


def test_public_package_api_and_version() -> None:
    agent = BDI(
        model=TestModel(),
        desires=["Prepare a project status report"],
        intentions=["Inspect project information"],
    )

    assert __version__ == distribution_version("voluntas")
    assert isinstance(agent, BDI)
    assert BDIUsageTracker is not None
    assert Belief is not None
    assert Desire is not None
    assert Intention is not None
