# Installation Guide

## Quick Start

### Using uv (Recommended - Fast!)

```bash
# Install uv if you haven't already
pip install uv

# Install base project
cd pydantic-ai-bdi
uv pip install -e .

# Install with all benchmark dependencies
uv pip install -e ".[benchmark-all]"
```

### Using pip

```bash
cd pydantic-ai-bdi

# Install base project
pip install -e .

# Install with all benchmark dependencies
pip install -e ".[benchmark-all]"
```

## Installation Options

> **Important**: All installation options include the **BDI Agent Framework** with its core dependencies (pydantic-ai, fastapi, etc.). This is required for running experiments and benchmarks.

### Base Installation

Just the BDI agent framework (no benchmarking):

```bash
uv pip install -e .
```

**Includes**:
- **BDI agent framework** (`bdi/`) - *Required for all experiments*
- Pydantic AI - *BDI's foundation*
- FastAPI server (`server/`)
- CLI tools
- Core dependencies (pydantic-ai, fastapi, uvicorn, python-dotenv, chardet)

### Benchmark Groups

All groups below **include the base BDI framework** plus additional tools:

Install specific benchmark features:

#### Core Benchmarking

```bash
uv pip install -e ".[benchmark]"
```

**Adds**:
- Statistical analysis (scipy, numpy)
- System metrics (psutil)
- TOML parsing (tomli)

#### Framework Support

```bash
uv pip install -e ".[frameworks]"
```

**Adds**:
- LangGraph (state machine agents)
- CrewAI (multi-agent systems)
- OpenAI API client
- LangChain dependencies

#### Visualization Tools

```bash
uv pip install -e ".[viz]"
```

**Adds**:
- Matplotlib (charts)
- Seaborn (statistical plots)
- Markdown (report generation)

#### All Benchmark Features

```bash
uv pip install -e ".[benchmark-all]"
```

**Includes everything**: benchmark + frameworks + viz

### Development Tools

```bash
uv pip install -e ".[dev]"
```

**Adds**:
- pytest (testing)
- black (formatting)
- ruff (linting)

### Multiple Groups

Install multiple groups at once:

```bash
uv pip install -e ".[benchmark-all,dev]"
```

## From benchmarks/ Directory

The `benchmarks/requirements.txt` file now references the root `pyproject.toml`:

```bash
cd benchmarks/

# Option 1: Use convenience script
./install-benchmarks.sh

# Option 2: Use pip/uv directly
pip install -r requirements.txt

# Option 3: Install from root
cd ..
uv pip install -e ".[benchmark-all]"
```

## Installation Verification

### Check Installation

```bash
# Check if BDI is installed
python -c "import bdi; print('BDI installed')"

# Check benchmark tools
python -c "import benchmarks; print('Benchmarks installed')"

# Check frameworks
python -c "import langgraph; print('LangGraph installed')"
python -c "import crewai; print('CrewAI installed')"
```

### Test Commands

```bash
# BDI agent server
start  # or: python -m cli

# Benchmark commands
benchmark-run --help
benchmark-analyze --help
benchmark-viz --help
experiment-run --help
```

## Platform-Specific Notes

### macOS

```bash
# May need to install OpenMP for NumPy/SciPy
brew install libomp
```

### Linux

```bash
# Usually no additional steps needed
```

### Windows

```bash
# Install Microsoft C++ Build Tools if needed
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

## Troubleshooting

### Issue: "command not found" for benchmark commands

**Solution**: Reinstall in editable mode:
```bash
uv pip install -e ".[benchmark-all]"
```

### Issue: Import errors for langgraph/crewai

**Solution**: Install frameworks group:
```bash
uv pip install -e ".[frameworks]"
```

### Issue: Matplotlib/Seaborn not found

**Solution**: Install visualization group:
```bash
uv pip install -e ".[viz]"
```

### Issue: "No module named benchmarks"

**Solution**: Make sure you're installing from project root:
```bash
cd /path/to/pydantic-ai-bdi
uv pip install -e ".[benchmark-all]"
```

## Environment Setup

### For Participants

Complete setup for running experiments:

```bash
# 1. Clone repository
git clone https://github.com/yourusername/pydantic-ai-bdi.git
cd pydantic-ai-bdi

# 2. Install uv (optional but recommended)
pip install uv

# 3. Install everything
uv pip install -e ".[benchmark-all]"

# 4. Set OpenAI API key
export OPENAI_API_KEY="your-key-here"

# 5. Test installation
python benchmarks/experiments/bdi/TEMPLATE.py
```

### For Researchers/Developers

```bash
# Install everything including dev tools
uv pip install -e ".[benchmark-all,dev]"

# Run tests
pytest

# Format code
black .

# Lint code
ruff check .
```

## Dependency Management

### Updating Dependencies

Edit `pyproject.toml` optional-dependencies sections:

```toml
[project.optional-dependencies]
benchmark = [
    "scipy>=1.11.0",
    # ... add more
]
```

Then reinstall:
```bash
uv pip install -e ".[benchmark-all]"
```

### Freezing Dependencies

Generate a lock file:

```bash
uv pip freeze > requirements-lock.txt
```

Install from lock file:
```bash
uv pip install -r requirements-lock.txt
```

## Why uv?

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

- **10-100x faster** than pip
- Drop-in replacement for pip
- Better dependency resolution
- Disk space caching

Install it:
```bash
pip install uv
```

Use it anywhere you'd use pip:
```bash
uv pip install <package>
uv pip install -e .
uv pip freeze
```

## Next Steps

After installation:

1. **Run your first benchmark**: See `BENCHMARKING.md`
2. **Start an experiment**: See `benchmarks/experiments/README.md`
3. **Explore the codebase**: See `README.md`

## Getting Help

- **Installation issues**: Check [Troubleshooting](#troubleshooting)
- **Usage questions**: See `BENCHMARKING.md` and `benchmarks/USAGE_GUIDE.md`
- **Bug reports**: Open an issue on GitHub
