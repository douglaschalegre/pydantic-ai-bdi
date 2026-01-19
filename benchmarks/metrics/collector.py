"""Metrics collection for benchmark runs."""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import psutil
import os


@dataclass
class MetricsCollector:
    """Collects metrics during task execution."""

    task_id: str
    framework: str
    model_name: str

    # Performance metrics
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    step_count: int = 0
    cycle_count: int = 0
    retry_count: int = 0
    human_intervention_count: int = 0

    # Resource metrics
    token_usage_input: int = 0
    token_usage_output: int = 0
    api_call_count: int = 0

    # Quality metrics
    beliefs_extracted: int = 0
    beliefs_accurate: int = 0
    plan_modifications: int = 0

    # System metrics
    cpu_usage_samples: List[float] = field(default_factory=list)
    memory_usage_samples: List[float] = field(default_factory=list)

    # Execution trace
    events: List[Dict[str, Any]] = field(default_factory=list)

    def start(self):
        """Start timing and resource monitoring."""
        self.start_time = time.time()
        self._record_system_metrics()

    def end(self):
        """End timing and resource monitoring."""
        self.end_time = time.time()
        self._record_system_metrics()

    def _record_system_metrics(self):
        """Record current system metrics."""
        try:
            process = psutil.Process()
            self.cpu_usage_samples.append(process.cpu_percent())
            self.memory_usage_samples.append(process.memory_info().rss / 1024 / 1024)  # MB
        except Exception:
            pass  # System metrics are optional

    def record_step(self, step_description: str, success: bool, tokens_in: int = 0, tokens_out: int = 0):
        """Record a step execution."""
        self.step_count += 1
        self.token_usage_input += tokens_in
        self.token_usage_output += tokens_out
        self.api_call_count += 1 if (tokens_in > 0 or tokens_out > 0) else 0

        if not success:
            self.retry_count += 1

        self.events.append({
            'type': 'step',
            'timestamp': time.time(),
            'description': step_description,
            'success': success,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
        })

        self._record_system_metrics()

    def record_cycle(self, cycle_number: int):
        """Record a BDI cycle completion."""
        self.cycle_count += 1

        self.events.append({
            'type': 'cycle',
            'timestamp': time.time(),
            'cycle_number': cycle_number,
        })

    def record_belief_extraction(self, count: int, accurate: int = None):
        """Record belief extraction."""
        self.beliefs_extracted += count
        if accurate is not None:
            self.beliefs_accurate += accurate

        self.events.append({
            'type': 'belief_extraction',
            'timestamp': time.time(),
            'count': count,
            'accurate': accurate,
        })

    def record_human_intervention(self, reason: str):
        """Record human intervention."""
        self.human_intervention_count += 1

        self.events.append({
            'type': 'human_intervention',
            'timestamp': time.time(),
            'reason': reason,
        })

    def record_plan_modification(self, modification_type: str):
        """Record plan modification."""
        self.plan_modifications += 1

        self.events.append({
            'type': 'plan_modification',
            'timestamp': time.time(),
            'modification_type': modification_type,
        })

    def record_error(self, error_message: str, error_type: str = "unknown"):
        """Record an error."""
        self.events.append({
            'type': 'error',
            'timestamp': time.time(),
            'error_message': error_message,
            'error_type': error_type,
        })

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0

        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time

    def get_average_cpu_usage(self) -> float:
        """Get average CPU usage."""
        if not self.cpu_usage_samples:
            return 0.0
        return sum(self.cpu_usage_samples) / len(self.cpu_usage_samples)

    def get_peak_memory_usage(self) -> float:
        """Get peak memory usage in MB."""
        if not self.memory_usage_samples:
            return 0.0
        return max(self.memory_usage_samples)

    def get_total_tokens(self) -> int:
        """Get total token usage."""
        return self.token_usage_input + self.token_usage_output

    def estimate_cost(self, input_cost_per_1k: float = 0.003, output_cost_per_1k: float = 0.015) -> float:
        """Estimate cost in USD based on token usage.

        Default costs are for GPT-4 pricing.
        Adjust based on actual model being used.
        """
        input_cost = (self.token_usage_input / 1000) * input_cost_per_1k
        output_cost = (self.token_usage_output / 1000) * output_cost_per_1k
        return input_cost + output_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'framework': self.framework,
            'model_name': self.model_name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'elapsed_time': self.get_elapsed_time(),
            'step_count': self.step_count,
            'cycle_count': self.cycle_count,
            'retry_count': self.retry_count,
            'human_intervention_count': self.human_intervention_count,
            'token_usage_input': self.token_usage_input,
            'token_usage_output': self.token_usage_output,
            'total_tokens': self.get_total_tokens(),
            'api_call_count': self.api_call_count,
            'estimated_cost_usd': self.estimate_cost(),
            'beliefs_extracted': self.beliefs_extracted,
            'beliefs_accurate': self.beliefs_accurate,
            'plan_modifications': self.plan_modifications,
            'average_cpu_usage': self.get_average_cpu_usage(),
            'peak_memory_mb': self.get_peak_memory_usage(),
            'event_count': len(self.events),
            'events': self.events,
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        return f"""
Metrics Summary for {self.task_id}
Framework: {self.framework}
Model: {self.model_name}

Performance:
- Execution Time: {self.get_elapsed_time():.2f}s
- Steps: {self.step_count}
- Cycles: {self.cycle_count}
- Retries: {self.retry_count}
- Human Interventions: {self.human_intervention_count}

Resources:
- Total Tokens: {self.get_total_tokens():,}
  - Input: {self.token_usage_input:,}
  - Output: {self.token_usage_output:,}
- API Calls: {self.api_call_count}
- Estimated Cost: ${self.estimate_cost():.4f}

System:
- Avg CPU: {self.get_average_cpu_usage():.1f}%
- Peak Memory: {self.get_peak_memory_usage():.1f} MB

Quality:
- Beliefs Extracted: {self.beliefs_extracted}
- Plan Modifications: {self.plan_modifications}
        """.strip()


class BenchmarkMetricsAggregator:
    """Aggregates metrics across multiple task executions."""

    def __init__(self):
        self.collectors: List[MetricsCollector] = []

    def add_collector(self, collector: MetricsCollector):
        """Add a metrics collector."""
        self.collectors.append(collector)

    def get_framework_metrics(self, framework: str) -> List[MetricsCollector]:
        """Get all collectors for a specific framework."""
        return [c for c in self.collectors if c.framework == framework]

    def get_task_metrics(self, task_id: str) -> List[MetricsCollector]:
        """Get all collectors for a specific task."""
        return [c for c in self.collectors if c.task_id == task_id]

    def get_average_metrics(self, framework: Optional[str] = None) -> Dict[str, float]:
        """Get average metrics across all collectors or for a specific framework."""
        collectors = self.get_framework_metrics(framework) if framework else self.collectors

        if not collectors:
            return {}

        return {
            'avg_elapsed_time': sum(c.get_elapsed_time() for c in collectors) / len(collectors),
            'avg_steps': sum(c.step_count for c in collectors) / len(collectors),
            'avg_cycles': sum(c.cycle_count for c in collectors) / len(collectors),
            'avg_retries': sum(c.retry_count for c in collectors) / len(collectors),
            'avg_human_interventions': sum(c.human_intervention_count for c in collectors) / len(collectors),
            'avg_tokens': sum(c.get_total_tokens() for c in collectors) / len(collectors),
            'avg_api_calls': sum(c.api_call_count for c in collectors) / len(collectors),
            'avg_cost': sum(c.estimate_cost() for c in collectors) / len(collectors),
            'total_cost': sum(c.estimate_cost() for c in collectors),
        }

    def get_framework_comparison(self) -> Dict[str, Dict[str, float]]:
        """Get comparison metrics across all frameworks."""
        frameworks = set(c.framework for c in self.collectors)
        return {
            framework: self.get_average_metrics(framework)
            for framework in frameworks
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'collectors': [c.to_dict() for c in self.collectors],
            'framework_comparison': self.get_framework_comparison(),
            'total_executions': len(self.collectors),
        }
