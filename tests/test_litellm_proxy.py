import pytest

from litellm_proxy import create_litellm_model
from pydantic_ai.models.openai import OpenAIChatModel


def test_create_litellm_model_uses_explicit_proxy_settings() -> None:
    model = create_litellm_model(
        "codex",
        base_url="http://127.0.0.1:4000",
        api_key="sk-test",
    )

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "codex"
    assert model._provider.base_url == "http://127.0.0.1:4000"


def test_create_litellm_model_reads_proxy_environment(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_BASE_URL", "http://localhost:4100")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-env")

    model = create_litellm_model("codex")

    assert model._provider.base_url == "http://localhost:4100"


def test_create_litellm_model_requires_authentication(monkeypatch) -> None:
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LITELLM_API_KEY"):
        create_litellm_model("codex")
