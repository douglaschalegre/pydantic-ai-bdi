"""Statistical analysis of benchmark results."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics
from collections import defaultdict

try:
    import scipy.stats as stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class StatisticalComparison:
    """Results of statistical comparison between frameworks."""

    metric_name: str
    framework1: str
    framework2: str

    mean1: float
    mean2: float
    std1: float
    std2: float

    # Statistical test results
    test_statistic: Optional[float] = None
    p_value: Optional[float] = None
    test_name: str = "t-test"

    # Effect size
    cohens_d: Optional[float] = None

    # Confidence intervals (95%)
    ci1_lower: Optional[float] = None
    ci1_upper: Optional[float] = None
    ci2_lower: Optional[float] = None
    ci2_upper: Optional[float] = None

    # Conclusion
    significant: bool = False
    significance_level: float = 0.05

    def get_interpretation(self) -> str:
        """Get human-readable interpretation."""
        if not self.significant:
            return f"No significant difference in {self.metric_name} between {self.framework1} and {self.framework2}"

        better = self.framework1 if self.mean1 < self.mean2 else self.framework2
        worse = self.framework2 if self.mean1 < self.mean2 else self.framework1

        effect_size_interp = ""
        if self.cohens_d is not None:
            abs_d = abs(self.cohens_d)
            if abs_d < 0.2:
                effect_size_interp = " (very small effect)"
            elif abs_d < 0.5:
                effect_size_interp = " (small effect)"
            elif abs_d < 0.8:
                effect_size_interp = " (medium effect)"
            else:
                effect_size_interp = " (large effect)"

        return f"{better} performs significantly better than {worse} on {self.metric_name}{effect_size_interp} (p={self.p_value:.4f})"


class BenchmarkAnalyzer:
    """Analyzes benchmark results with statistical rigor."""

    def __init__(self, results_dir: str):
        self.results_dir = Path(results_dir)
        self.task_results: List[Dict[str, Any]] = []
        self.framework_results: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def load_results(self):
        """Load all result files from results directory."""
        for file in self.results_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)

                    if 'task_results' in data:
                        # Benchmark run file
                        for result in data['task_results']:
                            self.task_results.append(result)
                            self.framework_results[result['framework']].append(result)
                    else:
                        # Individual result file
                        self.task_results.append(data)
                        self.framework_results[data['framework']].append(data)
            except Exception as e:
                print(f"Error loading {file}: {e}")

    def get_success_rate(self, framework: Optional[str] = None) -> float:
        """Calculate success rate."""
        results = self.framework_results[framework] if framework else self.task_results

        if not results:
            return 0.0

        successful = sum(1 for r in results if r.get('success', False))
        return successful / len(results)

    def get_metric_statistics(self, metric_name: str, framework: Optional[str] = None) -> Dict[str, float]:
        """Get statistics for a specific metric."""
        results = self.framework_results[framework] if framework else self.task_results

        values = [r.get(metric_name, 0) for r in results if metric_name in r]

        if not values:
            return {}

        stats_dict = {
            'count': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'min': min(values),
            'max': max(values),
        }

        if len(values) > 1:
            stats_dict['std'] = statistics.stdev(values)
            stats_dict['variance'] = statistics.variance(values)

        if len(values) >= 2:
            # Confidence interval (approximation using normal distribution)
            mean = stats_dict['mean']
            std = stats_dict.get('std', 0)
            n = len(values)
            margin = 1.96 * (std / (n ** 0.5))  # 95% CI
            stats_dict['ci_lower'] = mean - margin
            stats_dict['ci_upper'] = mean + margin

        return stats_dict

    def compare_frameworks(self, framework1: str, framework2: str, metric_name: str) -> StatisticalComparison:
        """Compare two frameworks on a specific metric using statistical tests."""
        values1 = [r.get(metric_name, 0) for r in self.framework_results[framework1] if metric_name in r]
        values2 = [r.get(metric_name, 0) for r in self.framework_results[framework2] if metric_name in r]

        if not values1 or not values2:
            return StatisticalComparison(
                metric_name=metric_name,
                framework1=framework1,
                framework2=framework2,
                mean1=0, mean2=0, std1=0, std2=0,
            )

        mean1 = statistics.mean(values1)
        mean2 = statistics.mean(values2)
        std1 = statistics.stdev(values1) if len(values1) > 1 else 0
        std2 = statistics.stdev(values2) if len(values2) > 1 else 0

        comparison = StatisticalComparison(
            metric_name=metric_name,
            framework1=framework1,
            framework2=framework2,
            mean1=mean1,
            mean2=mean2,
            std1=std1,
            std2=std2,
        )

        # Perform t-test if scipy available
        if SCIPY_AVAILABLE and len(values1) > 1 and len(values2) > 1:
            try:
                # Two-sample t-test
                t_stat, p_value = stats.ttest_ind(values1, values2)
                comparison.test_statistic = t_stat
                comparison.p_value = p_value
                comparison.significant = p_value < comparison.significance_level

                # Calculate Cohen's d (effect size)
                pooled_std = ((std1 ** 2 + std2 ** 2) / 2) ** 0.5
                if pooled_std > 0:
                    comparison.cohens_d = (mean1 - mean2) / pooled_std

                # Confidence intervals
                n1, n2 = len(values1), len(values2)
                se1 = std1 / (n1 ** 0.5) if n1 > 0 else 0
                se2 = std2 / (n2 ** 0.5) if n2 > 0 else 0

                comparison.ci1_lower = mean1 - 1.96 * se1
                comparison.ci1_upper = mean1 + 1.96 * se1
                comparison.ci2_lower = mean2 - 1.96 * se2
                comparison.ci2_upper = mean2 + 1.96 * se2

            except Exception as e:
                print(f"Error performing statistical test: {e}")

        return comparison

    def get_success_rate_comparison(self) -> Dict[str, Any]:
        """Compare success rates across frameworks using chi-square test."""
        framework_names = list(self.framework_results.keys())

        if len(framework_names) < 2:
            return {}

        # Build contingency table
        contingency = []
        for framework in framework_names:
            results = self.framework_results[framework]
            successful = sum(1 for r in results if r.get('success', False))
            failed = len(results) - successful
            contingency.append([successful, failed])

        comparison = {
            'frameworks': framework_names,
            'success_rates': {
                framework: self.get_success_rate(framework)
                for framework in framework_names
            },
            'counts': {
                framework: {
                    'successful': sum(1 for r in self.framework_results[framework] if r.get('success', False)),
                    'failed': sum(1 for r in self.framework_results[framework] if not r.get('success', False)),
                    'total': len(self.framework_results[framework]),
                }
                for framework in framework_names
            }
        }

        # Chi-square test if scipy available
        if SCIPY_AVAILABLE and len(framework_names) >= 2:
            try:
                chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
                comparison['chi_square'] = {
                    'statistic': chi2,
                    'p_value': p_value,
                    'degrees_of_freedom': dof,
                    'significant': p_value < 0.05,
                }
            except Exception as e:
                print(f"Error performing chi-square test: {e}")

        return comparison

    def get_task_category_analysis(self) -> Dict[str, Any]:
        """Analyze performance by task category."""
        category_results = defaultdict(lambda: defaultdict(list))

        for result in self.task_results:
            task_id = result.get('task_id', '')
            framework = result.get('framework', 'unknown')

            # Determine category from task_id
            if task_id.startswith('simple_'):
                category = 'simple'
            elif task_id.startswith('medium_'):
                category = 'medium'
            elif task_id.startswith('complex_'):
                category = 'complex'
            else:
                category = 'unknown'

            category_results[category][framework].append(result)

        analysis = {}
        for category, framework_data in category_results.items():
            analysis[category] = {
                'frameworks': {},
                'overall': {}
            }

            all_results = []
            for framework, results in framework_data.items():
                success_rate = sum(1 for r in results if r.get('success', False)) / len(results) if results else 0
                avg_time = statistics.mean([r.get('completion_time_seconds', 0) for r in results]) if results else 0

                analysis[category]['frameworks'][framework] = {
                    'count': len(results),
                    'success_rate': success_rate,
                    'avg_time': avg_time,
                }

                all_results.extend(results)

            # Overall stats for category
            if all_results:
                analysis[category]['overall'] = {
                    'count': len(all_results),
                    'success_rate': sum(1 for r in all_results if r.get('success', False)) / len(all_results),
                    'avg_time': statistics.mean([r.get('completion_time_seconds', 0) for r in all_results]),
                }

        return analysis

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive analysis report."""
        report_lines = [
            "# Benchmark Analysis Report",
            "",
            f"Total task executions: {len(self.task_results)}",
            f"Frameworks evaluated: {', '.join(self.framework_results.keys())}",
            "",
            "## Overall Success Rates",
            ""
        ]

        # Success rates
        for framework in self.framework_results.keys():
            rate = self.get_success_rate(framework)
            count = len(self.framework_results[framework])
            successful = int(rate * count)
            report_lines.append(f"- **{framework}**: {rate:.1%} ({successful}/{count} tasks)")

        report_lines.extend(["", "## Performance Metrics", ""])

        # Key metrics comparison
        metrics = ['completion_time_seconds', 'step_count', 'token_usage_input', 'token_usage_output', 'estimated_cost_usd']

        for metric in metrics:
            report_lines.append(f"### {metric.replace('_', ' ').title()}")
            report_lines.append("")

            for framework in self.framework_results.keys():
                stats_dict = self.get_metric_statistics(metric, framework)
                if stats_dict:
                    report_lines.append(
                        f"- **{framework}**: "
                        f"mean={stats_dict['mean']:.2f}, "
                        f"median={stats_dict['median']:.2f}, "
                        f"std={stats_dict.get('std', 0):.2f}"
                    )
            report_lines.append("")

        # Statistical comparisons
        frameworks = list(self.framework_results.keys())
        if len(frameworks) >= 2:
            report_lines.extend(["## Statistical Comparisons", ""])

            for i, fw1 in enumerate(frameworks):
                for fw2 in frameworks[i+1:]:
                    report_lines.append(f"### {fw1} vs {fw2}")
                    report_lines.append("")

                    for metric in ['completion_time_seconds', 'step_count']:
                        comparison = self.compare_frameworks(fw1, fw2, metric)
                        if comparison.p_value is not None:
                            report_lines.append(f"**{metric}**: {comparison.get_interpretation()}")

                    report_lines.append("")

        # Task category analysis
        category_analysis = self.get_task_category_analysis()
        if category_analysis:
            report_lines.extend(["## Performance by Task Category", ""])

            for category, data in category_analysis.items():
                report_lines.append(f"### {category.title()} Tasks")
                report_lines.append("")

                for framework, stats in data['frameworks'].items():
                    report_lines.append(
                        f"- **{framework}**: "
                        f"success={stats['success_rate']:.1%}, "
                        f"avg_time={stats['avg_time']:.1f}s"
                    )

                report_lines.append("")

        # Success rate comparison
        success_comparison = self.get_success_rate_comparison()
        if success_comparison:
            report_lines.extend(["## Success Rate Statistical Test", ""])

            if 'chi_square' in success_comparison:
                chi_sq = success_comparison['chi_square']
                report_lines.append(
                    f"Chi-square test: χ²={chi_sq['statistic']:.2f}, "
                    f"p={chi_sq['p_value']:.4f}, "
                    f"{'significant' if chi_sq['significant'] else 'not significant'}"
                )

        report = "\n".join(report_lines)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)

        return report

    def export_csv(self, output_file: str):
        """Export results to CSV format."""
        import csv

        if not self.task_results:
            return

        # Get all unique keys across all results
        all_keys = set()
        for result in self.task_results:
            all_keys.update(result.keys())

        fieldnames = sorted(all_keys)

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.task_results)
