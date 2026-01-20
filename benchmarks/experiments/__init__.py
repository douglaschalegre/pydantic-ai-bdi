"""Experiment framework for multi-participant benchmark studies.

This module provides templates and infrastructure for running controlled
experiments where multiple participants implement agents in different frameworks.
"""

from .base_experiment import (
    BaseExperiment,
    ExperimentMetrics,
    MetricCollector,
    collect_metrics,
)

__all__ = [
    'BaseExperiment',
    'ExperimentMetrics',
    'MetricCollector',
    'collect_metrics',
]
