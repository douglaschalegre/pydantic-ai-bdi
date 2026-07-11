from types import SimpleNamespace

from voluntas import usage as usage_module
from voluntas.usage import BDIUsageTracker


def test_usage_tracker_aggregates_usage_and_cost(monkeypatch) -> None:
    monkeypatch.setattr(
        usage_module,
        "_estimate_cost_usd",
        lambda _usage, _model_name: 0.012,
    )

    tracker = BDIUsageTracker(model_name="gpt-test")
    tracker.record_result(
        SimpleNamespace(
            usage=lambda: SimpleNamespace(
                requests=2,
                tool_calls=3,
                input_tokens=100,
                cache_read_tokens=40,
                cache_write_tokens=10,
                output_tokens=25,
                details={"reasoning_tokens": 7},
            )
        )
    )
    tracker.record_usage(
        SimpleNamespace(
            requests=1,
            tool_calls=0,
            input_tokens=50,
            output_tokens=5,
            details={"reasoning_tokens": 2},
        )
    )

    assert tracker.usage_summary() == {
        "requests": 3,
        "tool_calls": 3,
        "input_tokens": 150,
        "cached_input_tokens": 40,
        "cache_read_tokens": 40,
        "cache_write_tokens": 10,
        "input_audio_tokens": 0,
        "cache_audio_read_tokens": 0,
        "output_tokens": 30,
        "output_audio_tokens": 0,
        "total_tokens": 180,
        "details": {"reasoning_tokens": 9},
    }
    assert tracker.cost_summary() == {
        "usd": 0.024,
        "estimated": True,
        "priced_requests": 3,
        "unpriced_requests": 0,
    }


def test_usage_tracker_records_eval_metrics_and_attributes(monkeypatch) -> None:
    metrics: dict[str, float] = {}
    attributes: dict[str, object] = {}

    monkeypatch.setattr(
        usage_module,
        "_estimate_cost_usd",
        lambda _usage, _model_name: None,
    )
    monkeypatch.setattr(
        usage_module,
        "_increment_eval_metric",
        lambda name, amount: metrics.update({name: metrics.get(name, 0) + amount}),
    )
    monkeypatch.setattr(
        usage_module,
        "_set_eval_attribute",
        lambda name, value: attributes.update({name: value}),
    )

    tracker = BDIUsageTracker(model_name="gpt-test")
    tracker.record_usage(
        SimpleNamespace(
            requests=1,
            tool_calls=2,
            input_tokens=10,
            cache_read_tokens=4,
            output_tokens=3,
            details={"reasoning_tokens": 1},
        ),
        attributes={"bdi_cycle_count": 2},
    )

    assert metrics["requests"] == 1
    assert metrics["tool_calls"] == 2
    assert metrics["input_tokens"] == 10
    assert metrics["cached_input_tokens"] == 4
    assert metrics["output_tokens"] == 3
    assert metrics["total_tokens"] == 13
    assert metrics["reasoning_tokens"] == 1
    assert "cost" not in metrics
    assert attributes == {"model": "gpt-test", "bdi_cycle_count": 2}
