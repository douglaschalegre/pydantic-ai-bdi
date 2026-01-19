# BDI Agent Benchmarking Framework

Comprehensive benchmarking framework for evaluating and comparing the BDI (Belief-Desire-Intention) agent architecture against other agent frameworks for software engineering research.

## Overview

This framework provides:

1. **Task Suite**: 24+ carefully designed tasks across three complexity levels
2. **Multi-Participant Experiments**: Infrastructure for controlled studies with multiple participants
3. **Metrics Collection**: Comprehensive performance and quality metrics
4. **Statistical Analysis**: Rigorous statistical comparisons with effect sizes
5. **Framework Comparisons**: Head-to-head comparisons with LangGraph and CrewAI
6. **Usability Assessment**: Ease-of-use evaluation across multiple dimensions
7. **Visualization Tools**: Generate publication-quality charts and reports

## Two Modes of Use

### 1. Pre-Built Agent Comparison (Quick Evaluation)

Use the pre-implemented agents for quick comparisons:

```bash
python -m benchmarks.evaluation.runner --framework bdi --category simple
```

### 2. Multi-Participant Experiments (Scientific Research)

For rigorous scientific studies, multiple participants implement their own agents:

```bash
# Participant implements agents in experiments/{bdi,langgraph,crewai}/experiment-N.py
# Then runs:
python -m benchmarks.experiments.run_experiments --participant N
```

See `benchmarks/experiments/README.md` for complete participant guide.

## Quick Start

### Installation

#### Using uv (Recommended - Fast!)

```bash
# Install from project root
cd pydantic-ai-bdi
uv pip install -e ".[benchmark-all]"
```

#### Using pip

```bash
# Install from project root
cd pydantic-ai-bdi
pip install -e ".[benchmark-all]"

# Or use convenience script from benchmarks/
cd benchmarks/
./install-benchmarks.sh
```

See `INSTALLATION.md` for detailed options.

### Run First Benchmark

```bash
# Test with simple tasks
benchmark-run --framework bdi --category simple

# Or use full module path
python -m benchmarks.evaluation.runner --framework bdi --category simple
```

### Analyze Results

```bash
# Generate analysis report
python benchmarks/scripts/analyze_results.py benchmarks/results/run_*/
```

## Research Questions

This framework helps answer:

1. **Success Rate**: How reliably does BDI complete tasks vs other frameworks?
2. **Efficiency**: How does BDI perform on simple vs complex tasks?
3. **Cost**: What are the token/API cost trade-offs?
4. **Usability**: How easy is BDI to use compared to alternatives?
5. **Scalability**: How does BDI handle increasing task complexity?

## Benchmark Tasks

### Simple Tasks (8 tasks, ~1-2 min each)

- File operations (read, search, create)
- Basic data processing (JSON parsing, text transformation)
- Code analysis (count functions, git status)

**Example**: `simple_file_read` - Read a file and count lines

### Medium Tasks (8 tasks, ~2-10 min each)

- Multi-file analysis
- Dependency extraction
- Log analysis
- Documentation generation

**Example**: `medium_code_analysis` - Analyze directory structure and generate report

### Complex Tasks (8 tasks, ~10+ min each)

- Security audits
- Refactoring plans
- Test suite generation
- Architecture documentation

**Example**: `complex_codebase_audit` - Comprehensive security analysis

## Metrics Collected

### Performance Metrics
- Completion time
- Step count
- Retry count
- Human interventions (HITL)

### Resource Metrics
- Token usage (input/output)
- API call count
- Estimated cost (USD)

### Quality Metrics
- Success rate
- Success score (partial success)
- Plan efficiency
- Belief accuracy (BDI-specific)

### Usability Metrics
- Lines of code required
- Conceptual complexity
- Learning curve
- Documentation quality

## Framework Comparisons

This benchmark compares three major agent frameworks:

### BDI Agent (This Framework)
- **Architecture**: Belief-Desire-Intention
- **Strengths**: Explicit reasoning, plan reconsideration, HITL, belief tracking
- **Complexity**: Medium (5.5/10)
- **Best for**: Complex multi-step tasks requiring cognitive reasoning

### LangGraph
- **Architecture**: State machine graphs with conditional routing
- **Strengths**: Explicit control flow, composability, deterministic execution
- **Complexity**: High (6.5/10)
- **Best for**: Tasks with complex branching logic and state management

### CrewAI
- **Architecture**: Multi-agent collaboration with role-based organization
- **Strengths**: Role-based division, parallel execution, agent collaboration
- **Complexity**: Medium (5.0/10)
- **Best for**: Tasks requiring specialized roles working together

## Statistical Analysis

The framework provides:

- **Success Rate Comparison**: Chi-square tests for categorical outcomes
- **Performance Comparison**: t-tests for continuous metrics
- **Effect Size**: Cohen's d for practical significance
- **Confidence Intervals**: 95% CI for all metrics
- **Category Analysis**: Performance breakdown by task complexity

Example output:
```
BDI performs significantly better than LangGraph on completion_time_seconds
(medium effect) (p=0.0234)

Statistics:
  BDI: mean=45.2s, std=12.3s
  LangGraph: mean=67.8s, std=18.9s
  Cohen's d = 0.52
```

## Usage Examples

### Run Complete Study

```bash
# Run comprehensive benchmark across all frameworks
bash benchmarks/scripts/run_full_study.sh
```

### Compare Specific Frameworks

```bash
# Run BDI
python -m benchmarks.evaluation.runner --framework bdi

# Run LangGraph
python -m benchmarks.evaluation.runner --framework langgraph

# Run CrewAI
python -m benchmarks.evaluation.runner --framework crewai

# Analyze comparison
python benchmarks/scripts/analyze_results.py \
    benchmarks/results/run_*/ \
    --compare BDI LangGraph \
    --metric completion_time_seconds
```

### Generate Visualizations

```bash
# Create charts
python benchmarks/scripts/visualize_results.py \
    benchmarks/results/run_*/ \
    --output figures/

# Generates:
# - success_rates.png
# - completion_times.png
# - cost_comparison.png
# - category_performance.png
```

### Usability Assessment

```bash
# Generate usability report
python benchmarks/scripts/usability_report.py \
    --output usability_report.md
```

## Directory Structure

```
benchmarks/
├── README.md              # Framework overview
├── USAGE_GUIDE.md         # Detailed usage instructions
├── requirements.txt       # Python dependencies
├── .gitignore            # Ignore results directory
│
├── tasks/                 # Task definitions
│   ├── task_schema.py    # Task data structures
│   ├── simple_tasks.py   # 8 simple tasks
│   ├── medium_tasks.py   # 8 medium tasks
│   ├── complex_tasks.py  # 8 complex tasks
│   ├── validators.py     # Success criteria validators
│   └── setup_teardown.py # Task setup/cleanup functions
│
├── agents/                # Framework implementations
│   ├── base_agent.py     # Base interface
│   ├── bdi_agent.py      # BDI implementation
│   ├── pydantic_agent.py # Raw Pydantic AI
│   ├── langgraph_agent.py # LangGraph (stub)
│   └── crewai_agent.py   # CrewAI (stub)
│
├── metrics/               # Metrics and analysis
│   ├── collector.py      # Metrics collection
│   └── analyzer.py       # Statistical analysis
│
├── evaluation/            # Benchmark execution
│   └── runner.py         # Main benchmark runner
│
├── usability/             # Ease-of-use assessment
│   └── ease_of_use.py    # Usability evaluation
│
├── scripts/               # Helper scripts
│   ├── analyze_results.py    # CLI analysis tool
│   ├── visualize_results.py  # Generate charts
│   ├── usability_report.py   # Usability report
│   ├── combine_results.py    # Merge multiple runs
│   └── run_full_study.sh     # Complete study workflow
│
└── results/               # Results (gitignored)
    └── run_YYYYMMDD_HHMMSS/
        ├── benchmark_summary.json
        ├── framework_task.json
        ├── analysis_report.md
        ├── results.csv
        └── figures/
```

## Extending the Framework

### Add New Task

1. Define task in `tasks/simple_tasks.py` (or medium/complex)
2. Create validator in `tasks/validators.py`
3. Add setup/teardown if needed in `tasks/setup_teardown.py`
4. Run: `python -m benchmarks.evaluation.runner --tasks your_task_id`

See `USAGE_GUIDE.md` for detailed examples.

### Add New Framework

1. Create agent class in `agents/your_framework_agent.py`
2. Implement `BaseAgent` interface
3. Register in `evaluation/runner.py`
4. Run: `python -m benchmarks.evaluation.runner --framework your_framework`

See `USAGE_GUIDE.md` for implementation template.

## Results and Publications

Results from this framework can be used for:

- Academic papers on agent architectures
- Conference presentations
- Technical blog posts
- Framework comparisons
- Design decisions

### Citation

If you use this framework in research, please cite:

```bibtex
@software{pydantic_ai_bdi_benchmark,
  title={BDI Agent Benchmarking Framework},
  author={Your Name},
  year={2026},
  url={https://github.com/yourusername/pydantic-ai-bdi}
}
```

## Reproducibility

All benchmark runs include:

- Git commit hash
- Python version
- Package versions
- Model specifications
- Timestamp
- Random seed (where applicable)

This ensures reproducibility of results.

## Performance Tips

1. **Start small**: Test with simple tasks first
2. **Use appropriate models**: gpt-3.5-turbo for testing, gpt-4 for final runs
3. **Monitor costs**: Check estimated costs in results
4. **Run multiple times**: For statistical validity (3-5 runs recommended)
5. **Version control**: Tag benchmark configurations in git

## Cost Estimates

Approximate costs per full benchmark run (all 24 tasks):

- **GPT-3.5 Turbo**: ~$0.50 - $1.00
- **GPT-4**: ~$5.00 - $10.00
- **GPT-4 Turbo**: ~$2.00 - $5.00
- **Local models (Ollama)**: Free

Actual costs vary based on task complexity and framework efficiency.

## Troubleshooting

### Common Issues

**Tasks timing out**
- Increase timeout in task definition
- Use faster model for testing

**High costs**
- Use gpt-3.5-turbo for development
- Reduce number of tasks
- Use local models via Ollama

**Import errors**
- Ensure running from project root
- Install: `pip install -r benchmarks/requirements.txt`

**Framework not available**
- Check framework is installed (e.g., `pip install langgraph`)
- Verify registration in `runner.py`

See `USAGE_GUIDE.md` for more troubleshooting help.

## Contributing

Contributions welcome:

- New tasks (especially domain-specific)
- Framework implementations
- Validators
- Analysis tools
- Documentation improvements

Please submit pull requests with benchmark results demonstrating the changes work.

## License

Same as parent project (MIT)

## Documentation

- **README.md** (this file): Overview and quick start
- **USAGE_GUIDE.md**: Comprehensive usage instructions
- **tasks/**: Task definitions and validation
- **agents/**: Framework implementation examples

## Support

- **Issues**: Report bugs at GitHub Issues
- **Discussions**: Ask questions in GitHub Discussions
- **Documentation**: See USAGE_GUIDE.md for detailed help

---

**Ready to benchmark?**

```bash
# Quick start
pip install -r benchmarks/requirements.txt
python -m benchmarks.evaluation.runner --framework bdi --category simple
python benchmarks/scripts/analyze_results.py benchmarks/results/run_*/
```

Happy benchmarking! 🚀
