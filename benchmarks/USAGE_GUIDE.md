  # BDI Agent Benchmarking - Usage Guide

This guide explains how to run benchmarks, analyze results, and extend the framework for your research.

## Quick Start

### 1. Install Dependencies

```bash
# From the project root
pip install -r benchmarks/requirements.txt
```

### 2. Run Your First Benchmark

```bash
# Run simple tasks with BDI agent
python -m benchmarks.evaluation.runner --framework bdi --category simple

# Run all tasks with BDI agent
python -m benchmarks.evaluation.runner --framework bdi

# Run specific task
python -m benchmarks.evaluation.runner --framework bdi --tasks simple_file_read
```

### 3. Analyze Results

```bash
# Generate analysis report
python -m benchmarks.scripts.analyze_results benchmarks/results/run_20260117_120000
```

## Detailed Usage

### Running Benchmarks

#### Framework Selection

```bash
# Single framework
python -m benchmarks.evaluation.runner --framework bdi

# Multiple frameworks (comparison)
python -m benchmarks.evaluation.runner --framework bdi
python -m benchmarks.evaluation.runner --framework pydantic
python -m benchmarks.evaluation.runner --framework langgraph

# All frameworks at once
python -m benchmarks.evaluation.runner --all
```

#### Task Selection

```bash
# By category
python -m benchmarks.evaluation.runner --framework bdi --category simple
python -m benchmarks.evaluation.runner --framework bdi --category medium
python -m benchmarks.evaluation.runner --framework bdi --category complex

# Specific tasks
python -m benchmarks.evaluation.runner --framework bdi --tasks simple_file_read simple_file_search

# All tasks
python -m benchmarks.evaluation.runner --framework bdi
```

#### Model Selection

```bash
# OpenAI GPT-4
python -m benchmarks.evaluation.runner --framework bdi --model openai:gpt-4

# OpenAI GPT-3.5 (faster, cheaper)
python -m benchmarks.evaluation.runner --framework bdi --model openai:gpt-3.5-turbo

# Ollama local model
python -m benchmarks.evaluation.runner --framework bdi --model ollama:llama2

# Google Gemini (via Antigravity)
python -m benchmarks.evaluation.runner --framework bdi --model gemini:gemini-pro
```

#### Other Options

```bash
# Verbose output
python -m benchmarks.evaluation.runner --framework bdi --verbose

# Custom output directory
python -m benchmarks.evaluation.runner --framework bdi --output my_results/

# Full example
python -m benchmarks.evaluation.runner \
    --framework bdi \
    --category medium \
    --model openai:gpt-4 \
    --output results/experiment_1 \
    --verbose
```

### Analyzing Results

#### Using the Analyzer

```python
from benchmarks.metrics.analyzer import BenchmarkAnalyzer

# Load results
analyzer = BenchmarkAnalyzer("benchmarks/results/run_20260117_120000")
analyzer.load_results()

# Get success rates
bdi_success_rate = analyzer.get_success_rate("BDI")
pydantic_success_rate = analyzer.get_success_rate("Pydantic-AI")

print(f"BDI: {bdi_success_rate:.1%}")
print(f"Pydantic-AI: {pydantic_success_rate:.1%}")

# Get metric statistics
time_stats = analyzer.get_metric_statistics("completion_time_seconds", "BDI")
print(f"Average time: {time_stats['mean']:.2f}s")
print(f"Median time: {time_stats['median']:.2f}s")

# Compare frameworks
comparison = analyzer.compare_frameworks("BDI", "Pydantic-AI", "completion_time_seconds")
print(comparison.get_interpretation())

# Generate report
report = analyzer.generate_report("results/analysis_report.md")
print(report)
```

#### Command-Line Analysis

```bash
# Generate comprehensive report
python -m benchmarks.scripts.analyze_results \
    benchmarks/results/run_20260117_120000 \
    --output report.md

# Export to CSV
python -m benchmarks.scripts.analyze_results \
    benchmarks/results/run_20260117_120000 \
    --csv results.csv

# Compare specific frameworks
python -m benchmarks.scripts.analyze_results \
    benchmarks/results/run_20260117_120000 \
    --compare BDI Pydantic-AI
```

### Understanding Results

#### Result Files

Each benchmark run creates:

```
benchmarks/results/run_20260117_120000/
├── benchmark_summary.json          # Overall run summary
├── bdi_simple_file_read.json      # Individual task results
├── bdi_simple_file_search.json
└── ...
```

#### Benchmark Summary Structure

```json
{
  "run_id": "2026-01-17T12:00:00",
  "framework": "BDI",
  "model_name": "openai:gpt-4",
  "total_tasks": 8,
  "successful_tasks": 7,
  "failed_tasks": 1,
  "average_success_score": 0.875,
  "total_time_seconds": 245.6,
  "total_cost_usd": 0.234,
  "task_results": [...]
}
```

#### Task Result Structure

```json
{
  "task_id": "simple_file_read",
  "framework": "BDI",
  "success": true,
  "success_score": 1.0,
  "completion_time_seconds": 12.4,
  "step_count": 3,
  "cycle_count": 2,
  "retry_count": 0,
  "token_usage_input": 1234,
  "token_usage_output": 567,
  "estimated_cost_usd": 0.025,
  "criteria_met": ["File was successfully read", "Correct line count reported"],
  "criteria_failed": []
}
```

## Adding New Tasks

### 1. Define Task

Create a new task in `benchmarks/tasks/simple_tasks.py` (or medium/complex):

```python
TaskDefinition(
    id="simple_my_task",
    name="My Custom Task",
    description="Description of what this task does",
    category=TaskCategory.SIMPLE,
    domain=TaskDomain.FILE_OPS,
    tags=["custom", "test"],
    goal="Clear goal statement for the agent",
    initial_context={
        "key": "value",  # Initial information
    },
    tools_available=["read_file", "write_file"],
    success_criteria=[
        SuccessCriteria(
            description="Task completed successfully",
            validator="my_custom_validator",
            validator_params={"param": "value"}
        ),
    ],
    expected_min_steps=1,
    expected_max_steps=3,
    expected_time_seconds=15.0,
    timeout_seconds=60.0,
    difficulty_score=2.0,
)
```

### 2. Create Validator

Add validator to `benchmarks/tasks/validators.py`:

```python
def my_custom_validator(param: str, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Validate my custom criterion."""
    # Your validation logic here
    success = True  # or False based on validation

    return ValidationResult(
        success=success,
        message="Validation message",
        details={"key": "value"}
    )

# Register validator
VALIDATORS['my_custom_validator'] = my_custom_validator
```

### 3. Add Setup/Teardown (Optional)

In `benchmarks/tasks/setup_teardown.py`:

```python
def setup_my_task():
    """Setup for my task."""
    # Setup code
    pass

def cleanup_my_task():
    """Cleanup after my task."""
    # Cleanup code
    pass

# Register
SETUP_FUNCTIONS['setup_my_task'] = setup_my_task
TEARDOWN_FUNCTIONS['cleanup_my_task'] = cleanup_my_task
```

### 4. Run Your Task

```bash
python -m benchmarks.evaluation.runner --framework bdi --tasks simple_my_task
```

## Adding New Frameworks

### 1. Create Agent Implementation

Create `benchmarks/agents/my_framework_agent.py`:

```python
from benchmarks.agents.base_agent import BaseAgent, AgentExecutionResult, Tool

class MyFrameworkAgent(BaseAgent):
    """My framework implementation."""

    async def execute_task(
        self,
        goal: str,
        initial_context: Dict[str, Any],
        tools_available: List[str],
    ) -> AgentExecutionResult:
        """Execute task using my framework."""

        # Your framework-specific implementation
        success = False
        final_state = {}
        execution_log = ""

        # ... implementation ...

        return AgentExecutionResult(
            success=success,
            final_state=final_state,
            execution_log=execution_log,
            steps_executed=0,
            tokens_used_input=0,
            tokens_used_output=0,
            api_calls_made=0,
        )

    def get_framework_name(self) -> str:
        return "MyFramework"

    def get_lines_of_code_required(self) -> int:
        return 35  # Approximate LOC for typical setup

    def get_complexity_score(self) -> float:
        return 4.5  # 1.0 (simple) to 10.0 (complex)

    # ... implement other abstract methods ...
```

### 2. Register Framework

In `benchmarks/evaluation/runner.py`:

```python
from benchmarks.agents.my_framework_agent import MyFrameworkAgent

FRAMEWORKS = {
    'bdi': BDIBenchmarkAgent,
    'pydantic': PydanticAIAgent,
    'langgraph': LangGraphAgent,
    'crewai': CrewAIAgent,
    'myframework': MyFrameworkAgent,  # Add here
}
```

### 3. Run Benchmark

```bash
python -m benchmarks.evaluation.runner --framework myframework
```

## Usability Assessment

### Generate Usability Report

```python
from benchmarks.usability.ease_of_use import create_standard_assessments

evaluator = create_standard_assessments()
report = evaluator.generate_report()

with open("usability_report.md", "w") as f:
    f.write(report)
```

### Compare Frameworks

```python
comparison = evaluator.compare_frameworks("BDI", "Pydantic-AI")
print(f"Winner: {comparison['winner']}")
print(f"BDI score: {comparison['overall_scores']['BDI']:.1f}")
print(f"Pydantic-AI score: {comparison['overall_scores']['Pydantic-AI']:.1f}")
```

## Research Workflow

### Complete Benchmark Study

```bash
# 1. Run benchmarks for all frameworks
python -m benchmarks.evaluation.runner --framework bdi --all
python -m benchmarks.evaluation.runner --framework pydantic --all
python -m benchmarks.evaluation.runner --framework langgraph --all
python -m benchmarks.evaluation.runner --framework crewai --all

# 2. Analyze results
python -m benchmarks.scripts.analyze_results \
    benchmarks/results/run_20260117_120000 \
    --output analysis_report.md \
    --csv results.csv

# 3. Generate visualizations
python -m benchmarks.scripts.visualize_results \
    benchmarks/results/run_20260117_120000 \
    --output figures/

# 4. Generate usability report
python -m benchmarks.scripts.usability_report \
    --output usability_report.md
```

### Statistical Analysis

```python
from benchmarks.metrics.analyzer import BenchmarkAnalyzer

analyzer = BenchmarkAnalyzer("benchmarks/results/run_20260117_120000")
analyzer.load_results()

# Success rate comparison (chi-square test)
success_comparison = analyzer.get_success_rate_comparison()
if 'chi_square' in success_comparison:
    chi_sq = success_comparison['chi_square']
    print(f"χ² = {chi_sq['statistic']:.2f}")
    print(f"p = {chi_sq['p_value']:.4f}")
    print(f"Significant: {chi_sq['significant']}")

# Performance comparison (t-test)
comparison = analyzer.compare_frameworks("BDI", "Pydantic-AI", "completion_time_seconds")
print(comparison.get_interpretation())

# Effect size (Cohen's d)
if comparison.cohens_d:
    print(f"Cohen's d = {comparison.cohens_d:.2f}")
```

## Tips and Best Practices

### 1. Start Small

Run simple tasks first to verify setup:

```bash
python -m benchmarks.evaluation.runner --framework bdi --tasks simple_file_read
```

### 2. Use Appropriate Models

- **Development/Testing**: Use cheaper models (gpt-3.5-turbo)
- **Final Benchmarks**: Use consistent model across all frameworks

### 3. Monitor Costs

Track estimated costs in results:

```python
total_cost = sum(r['estimated_cost_usd'] for r in task_results)
print(f"Total cost: ${total_cost:.2f}")
```

### 4. Run Multiple Times

For statistical validity, run each benchmark multiple times:

```bash
for i in {1..5}; do
    python -m benchmarks.evaluation.runner --framework bdi --output results/run_$i
done
```

### 5. Version Control

Track benchmark configurations:

```bash
git add benchmarks/
git commit -m "Add benchmark run configuration"
git tag benchmark-v1.0
```

## Troubleshooting

### Common Issues

**Issue**: Tasks timing out

**Solution**: Increase timeout in task definition or use faster model

**Issue**: High costs

**Solution**: Use gpt-3.5-turbo for development, or local models via Ollama

**Issue**: Import errors

**Solution**: Ensure you're running from project root and dependencies are installed

**Issue**: Framework not found

**Solution**: Check framework is registered in `FRAMEWORKS` dict in `runner.py`

### Getting Help

1. Check task execution logs in results files
2. Run with `--verbose` flag for detailed output
3. Review task definitions and validators
4. Check framework-specific documentation

## Citation

If using this benchmark framework in research, please cite:

```bibtex
@software{pydantic_ai_bdi_benchmark,
  title={BDI Agent Benchmarking Framework},
  author={Your Name},
  year={2026},
  url={https://github.com/yourusername/pydantic-ai-bdi}
}
```

## Contributing

To contribute new tasks or frameworks:

1. Fork the repository
2. Add your tasks/frameworks following the patterns above
3. Run benchmarks to verify
4. Submit pull request with results

## License

Same as parent project (MIT)
