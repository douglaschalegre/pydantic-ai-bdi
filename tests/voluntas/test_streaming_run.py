from pydantic_ai.models.test import TestModel

import pytest

from voluntas import BDI


@pytest.mark.asyncio
async def test_stream_model_requests_materializes_text_result() -> None:
    agent = BDI(model=TestModel(), stream_model_requests=True)

    result = await agent.run("Reply with a short answer.")

    assert isinstance(result.output, str)
    assert result.output


@pytest.mark.asyncio
async def test_stream_model_requests_materializes_structured_result() -> None:
    from pydantic import BaseModel

    class Answer(BaseModel):
        value: str

    agent = BDI(model=TestModel(), stream_model_requests=True)

    result = await agent.run("Return a short answer.", output_type=Answer)

    assert isinstance(result.output, Answer)
