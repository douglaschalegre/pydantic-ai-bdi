# Dependency Graph

## Most Imported Files (change these carefully)

- `/constants.py` — imported by **4** files
- `/auth.py` — imported by **2** files
- `/provider.py` — imported by **2** files
- `/task_schema.py` — imported by **4** files
- `/model.py` — imported by **1** files
- `/base_agent.py` — imported by **1** files
- `/bdi_agent.py` — imported by **1** files
- `/langgraph_agent.py` — imported by **1** files
- `/crewai_agent.py` — imported by **1** files
- `/runner.py` — imported by **1** files
- `/base_experiment.py` — imported by **1** files
- `/collector.py` — imported by **1** files
- `/usage_tracker.py` — imported by **1** files
- `/simple_tasks.py` — imported by **1** files
- `/medium_tasks.py` — imported by **1** files
- `/complex_tasks.py` — imported by **1** files
- `/ease_of_use.py` — imported by **1** files

## Import Map (who imports what)

- `/constants.py` ← `codex/__init__.py`, `codex/auth.py`, `codex/model.py`, `codex/provider.py`
- `/auth.py` ← `codex/__init__.py`, `codex/provider.py`
- `/provider.py` ← `codex/__init__.py`, `codex/model.py`
- `/task_schema.py` ← `benchmarks/tasks/__init__.py`, `benchmarks/tasks/complex_tasks.py`, `benchmarks/tasks/medium_tasks.py`, `benchmarks/tasks/simple_tasks.py`
- `/model.py` ← `codex/__init__.py`
- `/base_agent.py` ← `benchmarks/agents/__init__.py`
- `/bdi_agent.py` ← `benchmarks/agents/__init__.py`
- `/langgraph_agent.py` ← `benchmarks/agents/__init__.py`
- `/crewai_agent.py` ← `benchmarks/agents/__init__.py`
