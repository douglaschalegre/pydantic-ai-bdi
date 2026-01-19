"""Task schema definitions for benchmarking."""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class TaskCategory(str, Enum):
    """Task complexity categories."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class TaskDomain(str, Enum):
    """Task domain categories."""
    FILE_OPS = "file_operations"
    DATA_PROCESSING = "data_processing"
    CODE_ANALYSIS = "code_analysis"
    API_INTEGRATION = "api_integration"
    DEBUGGING = "debugging"
    RESEARCH = "research"
    MULTI_STEP = "multi_step_workflow"


class SuccessCriteria(BaseModel):
    """Defines how to evaluate task success."""

    description: str = Field(description="Human-readable success condition")
    validator: str = Field(description="Name of validation function to call")
    validator_params: Dict[str, Any] = Field(default_factory=dict)
    required: bool = Field(default=True, description="Whether this criterion is required")
    weight: float = Field(default=1.0, description="Weight for partial success scoring")


class TaskDefinition(BaseModel):
    """Complete task definition for benchmarking."""

    # Identity
    id: str = Field(description="Unique task identifier")
    name: str = Field(description="Human-readable task name")
    description: str = Field(description="Detailed task description")

    # Classification
    category: TaskCategory
    domain: TaskDomain
    tags: List[str] = Field(default_factory=list)

    # Task specification
    goal: str = Field(description="High-level goal statement")
    initial_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context provided to agent at start"
    )
    tools_available: List[str] = Field(
        default_factory=list,
        description="List of tool names available for this task"
    )

    # Success evaluation
    success_criteria: List[SuccessCriteria] = Field(
        description="Criteria for evaluating success"
    )
    expected_min_steps: int = Field(description="Minimum reasonable steps")
    expected_max_steps: int = Field(description="Maximum reasonable steps")
    expected_time_seconds: float = Field(description="Expected completion time")

    # Constraints
    timeout_seconds: float = Field(default=600.0, description="Maximum allowed time")
    max_retries: int = Field(default=3, description="Maximum retries per step")
    allow_human_intervention: bool = Field(default=False)

    # Setup and teardown
    setup_function: Optional[str] = Field(
        default=None,
        description="Name of function to call before task"
    )
    teardown_function: Optional[str] = Field(
        default=None,
        description="Name of function to call after task"
    )

    # Metadata for analysis
    difficulty_score: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="Subjective difficulty rating"
    )
    requires_external_api: bool = Field(default=False)
    requires_file_system: bool = Field(default=True)
    requires_code_execution: bool = Field(default=False)


class TaskResult(BaseModel):
    """Result of executing a task."""

    # Task identity
    task_id: str
    framework: str
    run_id: str

    # Execution results
    success: bool
    success_score: float = Field(ge=0.0, le=1.0, description="Partial success score")
    completion_time_seconds: float
    error_message: Optional[str] = None

    # Performance metrics
    step_count: int
    cycle_count: Optional[int] = None  # BDI-specific
    retry_count: int
    human_intervention_count: int

    # Resource metrics
    token_usage_input: int
    token_usage_output: int
    api_call_count: int
    estimated_cost_usd: float

    # Quality metrics
    criteria_met: List[str] = Field(default_factory=list)
    criteria_failed: List[str] = Field(default_factory=list)
    partial_criteria: Dict[str, float] = Field(default_factory=dict)

    # Execution trace
    execution_log: str = Field(default="")
    final_state: Dict[str, Any] = Field(default_factory=dict)

    # Environment
    model_name: str
    framework_version: str
    git_commit: Optional[str] = None
    timestamp: float


class BenchmarkRun(BaseModel):
    """Collection of task results from a benchmark run."""

    run_id: str
    framework: str
    model_name: str
    timestamp: float
    git_commit: Optional[str] = None

    task_results: List[TaskResult]

    # Summary statistics
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    average_success_score: float
    total_time_seconds: float
    total_cost_usd: float

    # Environment details
    python_version: str
    os_platform: str
    environment_vars: Dict[str, str] = Field(default_factory=dict)
