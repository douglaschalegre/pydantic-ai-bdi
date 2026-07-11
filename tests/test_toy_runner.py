import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import toy
from sbench_toy import config as toy_config
from sbench_toy import tools as toy_tools


def make_sbench_root(tmp_path: Path, task_id: str = "task-a") -> Path:
    sbench_root = tmp_path / "sbench"
    task_path = sbench_root / "tasks" / task_id
    task_path.mkdir(parents=True)
    (task_path / "task.md").write_text(f"# {task_id}\n", encoding="utf-8")
    return sbench_root


def test_parse_config_accepts_orchestrator_command_options(tmp_path: Path) -> None:
    sbench_root = tmp_path / "sbench"

    config = toy_config.parse_config(
        [
            "--sbench-root",
            str(sbench_root),
            "--tasks",
            "task-a",
            "--model",
            "gpt-test",
            "--command-timeout-seconds",
            "12",
            "--quiet",
        ]
    )

    assert config == toy_config.RunConfig(
        task_id="task-a",
        model_name="gpt-test",
        sbench_root=sbench_root,
        command_timeout_seconds=12,
        verbose=False,
    )


def test_parse_config_requires_explicit_single_task() -> None:
    with pytest.raises(SystemExit):
        toy_config.parse_config([])


def test_get_task_path_resolves_selected_task(tmp_path: Path) -> None:
    sbench_root = make_sbench_root(tmp_path)

    task_path = toy_config.get_task_path(
        toy_config.RunConfig(task_id="task-a", sbench_root=sbench_root)
    )

    assert task_path == sbench_root / "tasks" / "task-a"


def test_get_task_path_rejects_missing_task_file(tmp_path: Path) -> None:
    config = toy_config.RunConfig(
        task_id="missing-task",
        sbench_root=tmp_path / "sbench",
    )

    with pytest.raises(toy_config.RunnerConfigError, match="SBench task file not found"):
        toy_config.get_task_path(config)


def test_run_command_uses_task_cwd_and_clamps_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {}

    def fake_run(command, *, shell, cwd, capture_output, text, timeout):
        captured.update(
            command=command,
            shell=shell,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )
        return SimpleNamespace(stdout="ok\n", stderr="", returncode=0)

    monkeypatch.setattr(toy_tools.subprocess, "run", fake_run)

    result = toy_tools.run_command(
        tmp_path / "task-a",
        "pwd",
        timeout_seconds=999,
        max_timeout_seconds=17,
    )

    assert result == "ok"
    assert captured == {
        "command": "pwd",
        "shell": True,
        "cwd": str(tmp_path / "task-a"),
        "capture_output": True,
        "text": True,
        "timeout": 17,
    }


def test_create_agent_scopes_run_tool_and_usage_tracker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {}

    class FakeBDI:
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def tool_plain(self, func):
            captured["tool"] = func
            return func

    def fake_run_command(task_path, command, *, timeout_seconds, max_timeout_seconds):
        captured["run_command"] = {
            "task_path": task_path,
            "command": command,
            "timeout_seconds": timeout_seconds,
            "max_timeout_seconds": max_timeout_seconds,
        }
        return "ran"

    monkeypatch.setattr(toy, "BDI", FakeBDI)
    monkeypatch.setattr(toy, "run_command", fake_run_command)
    task_path = tmp_path / "tasks" / "task-a"
    usage_tracker = object()
    config = toy_config.RunConfig(
        task_id="task-a",
        command_timeout_seconds=9,
        verbose=False,
    )

    agent = toy.create_agent(
        "model",
        task_path,
        config,
        usage_tracker,
    )
    result = captured["tool"]("ls", timeout_seconds=99)

    assert isinstance(agent, FakeBDI)
    assert captured["args"] == ("model",)
    assert captured["kwargs"]["verbose"] is False
    assert "log_file_path" not in captured["kwargs"]
    assert captured["kwargs"]["usage_tracker"] is usage_tracker
    assert captured["kwargs"]["emit_run_events_to_stdout"] is True
    assert "structured_log_file_path" not in captured["kwargs"]
    assert captured["kwargs"]["mcp_servers"] == []
    assert "Do not read hidden SBench evaluation files" in captured["kwargs"]["desires"][0]
    assert result == "ran"
    assert captured["run_command"] == {
        "task_path": task_path,
        "command": "ls",
        "timeout_seconds": 99,
        "max_timeout_seconds": 9,
    }


@pytest.mark.asyncio
async def test_run_task_emits_usage_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_path = tmp_path / "tasks" / "task-a"
    task_path.mkdir(parents=True)
    config = toy_config.RunConfig(
        task_id="task-a",
        model_name="gpt-test",
        verbose=False,
    )

    class FakeRunMCPServers:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAgent:
        def __init__(self, usage_tracker):
            self.usage_tracker = usage_tracker
            self.beliefs = SimpleNamespace(beliefs={"task": "done"})
            self.desires = [SimpleNamespace(id="desire_1", status=toy.DesireStatus.ACHIEVED)]
            self.intentions = []
            self.cycle_count = 1

        def run_mcp_servers(self):
            return FakeRunMCPServers()

        async def bdi_cycle(self):
            self.usage_tracker.record_usage(
                SimpleNamespace(
                    requests=2,
                    tool_calls=1,
                    input_tokens=100,
                    cache_read_tokens=60,
                    output_tokens=20,
                )
            )
            return "terminal"

    def fake_create_agent(
        model,
        task_path,
        config,
        usage_tracker=None,
    ):
        assert model == "model"
        assert task_path.name == "task-a"
        assert usage_tracker is not None
        return FakeAgent(usage_tracker)

    monkeypatch.setattr(toy, "create_agent", fake_create_agent)

    outcome = await toy.run_task("model", task_path, config)

    assert outcome == "achieved"
    metadata = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert metadata["type"] == "voluntas.run.completed"
    assert metadata["model"] == "gpt-test"
    assert metadata["task"] == "task-a"
    assert metadata["outcome"] == "achieved"
    assert "structured_log_file" not in metadata
    assert metadata["cycles"] == {"run": 1, "max": toy.MAX_CYCLES}
    assert metadata["usage"]["requests"] == 2
    assert metadata["usage"]["tool_calls"] == 1
    assert metadata["usage"]["input_tokens"] == 100
    assert metadata["usage"]["cached_input_tokens"] == 60
    assert metadata["usage"]["output_tokens"] == 20
    assert metadata["usage"]["total_tokens"] == 120
    assert metadata["cost"]["estimated"] is False
    assert metadata["voluntas"]["beliefs"] == 1
    assert metadata["voluntas"]["desires"] == [
        {"id": "desire_1", "status": "achieved"}
    ]


@pytest.mark.asyncio
async def test_run_benchmark_runs_one_selected_task_and_returns_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sbench_root = make_sbench_root(tmp_path)
    config = toy_config.RunConfig(
        task_id="task-a",
        sbench_root=sbench_root,
    )
    task_calls = []

    monkeypatch.setattr(toy, "create_model", lambda run_config: ("model", run_config))

    async def fake_run_task(model, task_path, run_config):
        task_calls.append((model, task_path.name, run_config))
        return "achieved"

    monkeypatch.setattr(toy, "run_task", fake_run_task)

    exit_code = await toy.run_benchmark(config)

    assert exit_code == toy.EXIT_SUCCESS
    assert task_calls == [(("model", config), "task-a", config)]


@pytest.mark.asyncio
async def test_run_benchmark_returns_failure_for_non_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sbench_root = make_sbench_root(tmp_path)
    config = toy_config.RunConfig(task_id="task-a", sbench_root=sbench_root)

    monkeypatch.setattr(toy, "create_model", lambda _config: "model")
    monkeypatch.setattr(toy, "run_task", lambda *_args: _async_result("error"))

    assert await toy.run_benchmark(config) == toy.EXIT_TASK_FAILURE


async def _async_result(value: str) -> str:
    return value


@pytest.mark.asyncio
async def test_main_returns_config_error_for_missing_sbench_root(
    tmp_path: Path,
) -> None:
    exit_code = await toy.main(
        ["--sbench-root", str(tmp_path / "missing"), "--tasks", "task-a"]
    )

    assert exit_code == toy.EXIT_CONFIG_ERROR
