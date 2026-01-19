"""Ease-of-use assessment framework for agent frameworks."""

from typing import Any, Dict, List
from dataclasses import dataclass
from enum import Enum


class UsabilityDimension(str, Enum):
    """Dimensions for evaluating ease of use."""
    SETUP_COMPLEXITY = "setup_complexity"
    CONCEPTUAL_CLARITY = "conceptual_clarity"
    CODE_READABILITY = "code_readability"
    DEBUGGING_EASE = "debugging_ease"
    DOCUMENTATION_QUALITY = "documentation_quality"
    ERROR_MESSAGES = "error_messages"
    LEARNING_CURVE = "learning_curve"


@dataclass
class UsabilityMetric:
    """Single usability metric measurement."""

    dimension: UsabilityDimension
    score: float  # 1.0 (poor) to 10.0 (excellent)
    description: str
    evidence: str


@dataclass
class UsabilityAssessment:
    """Complete usability assessment for a framework."""

    framework_name: str
    metrics: List[UsabilityMetric]

    # Quantitative metrics
    lines_of_code_required: int
    cyclomatic_complexity: float
    number_of_concepts: int  # e.g., BDI has 3 core concepts: beliefs, desires, intentions

    # Qualitative assessments
    onboarding_time_estimate_hours: float
    expertise_required: str  # "beginner", "intermediate", "expert"

    def get_overall_score(self) -> float:
        """Calculate overall usability score."""
        if not self.metrics:
            return 0.0

        return sum(m.score for m in self.metrics) / len(self.metrics)

    def get_dimension_score(self, dimension: UsabilityDimension) -> float:
        """Get score for specific dimension."""
        scores = [m.score for m in self.metrics if m.dimension == dimension]
        return sum(scores) / len(scores) if scores else 0.0


class EaseOfUseEvaluator:
    """Evaluates and compares ease of use across frameworks."""

    def __init__(self):
        self.assessments: Dict[str, UsabilityAssessment] = {}

    def assess_framework(
        self,
        framework_name: str,
        lines_of_code: int,
        complexity: float,
        concepts: int,
        onboarding_hours: float,
        expertise: str,
    ) -> UsabilityAssessment:
        """Create usability assessment for a framework."""

        metrics = []

        # Setup Complexity (inverse of LOC - fewer lines = simpler)
        loc_score = max(1.0, 10.0 - (lines_of_code / 10.0))
        metrics.append(UsabilityMetric(
            dimension=UsabilityDimension.SETUP_COMPLEXITY,
            score=loc_score,
            description="How complex is the initial setup?",
            evidence=f"{lines_of_code} lines of code required"
        ))

        # Conceptual Clarity (inverse of number of concepts)
        concept_score = max(1.0, 10.0 - concepts)
        metrics.append(UsabilityMetric(
            dimension=UsabilityDimension.CONCEPTUAL_CLARITY,
            score=concept_score,
            description="How clear and simple are the core concepts?",
            evidence=f"{concepts} core concepts to learn"
        ))

        # Code Readability (inverse of cyclomatic complexity)
        readability_score = max(1.0, 10.0 - complexity)
        metrics.append(UsabilityMetric(
            dimension=UsabilityDimension.CODE_READABILITY,
            score=readability_score,
            description="How readable is the resulting code?",
            evidence=f"Complexity score: {complexity}"
        ))

        # Learning Curve (inverse of onboarding time)
        learning_score = max(1.0, 10.0 - (onboarding_hours / 2.0))
        metrics.append(UsabilityMetric(
            dimension=UsabilityDimension.LEARNING_CURVE,
            score=learning_score,
            description="How steep is the learning curve?",
            evidence=f"~{onboarding_hours} hours to proficiency"
        ))

        assessment = UsabilityAssessment(
            framework_name=framework_name,
            metrics=metrics,
            lines_of_code_required=lines_of_code,
            cyclomatic_complexity=complexity,
            number_of_concepts=concepts,
            onboarding_time_estimate_hours=onboarding_hours,
            expertise_required=expertise,
        )

        self.assessments[framework_name] = assessment
        return assessment

    def compare_frameworks(self, framework1: str, framework2: str) -> Dict[str, Any]:
        """Compare usability between two frameworks."""

        if framework1 not in self.assessments or framework2 not in self.assessments:
            return {"error": "Framework not assessed"}

        a1 = self.assessments[framework1]
        a2 = self.assessments[framework2]

        comparison = {
            "framework1": framework1,
            "framework2": framework2,
            "overall_scores": {
                framework1: a1.get_overall_score(),
                framework2: a2.get_overall_score(),
            },
            "winner": framework1 if a1.get_overall_score() > a2.get_overall_score() else framework2,
            "dimension_comparison": {},
        }

        # Compare each dimension
        for dimension in UsabilityDimension:
            score1 = a1.get_dimension_score(dimension)
            score2 = a2.get_dimension_score(dimension)

            comparison["dimension_comparison"][dimension.value] = {
                framework1: score1,
                framework2: score2,
                "difference": score1 - score2,
                "better": framework1 if score1 > score2 else framework2,
            }

        return comparison

    def generate_report(self) -> str:
        """Generate usability comparison report."""

        lines = [
            "# Framework Usability Assessment Report",
            "",
            "## Overview",
            "",
            f"Frameworks assessed: {len(self.assessments)}",
            "",
        ]

        # Framework summaries
        for framework, assessment in self.assessments.items():
            lines.extend([
                f"### {framework}",
                "",
                f"**Overall Score**: {assessment.get_overall_score():.1f}/10.0",
                "",
                "**Quantitative Metrics**:",
                f"- Lines of Code: {assessment.lines_of_code_required}",
                f"- Complexity: {assessment.cyclomatic_complexity:.1f}",
                f"- Core Concepts: {assessment.number_of_concepts}",
                f"- Onboarding Time: ~{assessment.onboarding_time_estimate_hours} hours",
                f"- Expertise Required: {assessment.expertise_required}",
                "",
                "**Dimension Scores**:",
            ])

            for metric in assessment.metrics:
                lines.append(f"- {metric.dimension.value}: {metric.score:.1f}/10.0 - {metric.evidence}")

            lines.append("")

        # Rankings
        lines.extend([
            "## Overall Rankings",
            "",
        ])

        ranked = sorted(
            self.assessments.items(),
            key=lambda x: x[1].get_overall_score(),
            reverse=True
        )

        for rank, (framework, assessment) in enumerate(ranked, 1):
            lines.append(
                f"{rank}. **{framework}**: {assessment.get_overall_score():.1f}/10.0"
            )

        lines.append("")

        # Dimension-specific rankings
        for dimension in UsabilityDimension:
            lines.extend([
                f"## Best for {dimension.value.replace('_', ' ').title()}",
                "",
            ])

            ranked_dim = sorted(
                self.assessments.items(),
                key=lambda x: x[1].get_dimension_score(dimension),
                reverse=True
            )

            for rank, (framework, assessment) in enumerate(ranked_dim, 1):
                score = assessment.get_dimension_score(dimension)
                if score > 0:
                    lines.append(f"{rank}. **{framework}**: {score:.1f}/10.0")

            lines.append("")

        return "\n".join(lines)


# Pre-defined assessments based on framework characteristics

def create_standard_assessments() -> EaseOfUseEvaluator:
    """Create standard usability assessments for frameworks.

    Compares BDI against LangGraph and CrewAI.
    """

    evaluator = EaseOfUseEvaluator()

    # BDI Framework
    evaluator.assess_framework(
        framework_name="BDI",
        lines_of_code=40,
        complexity=5.5,
        concepts=5,  # Beliefs, Desires, Intentions, Cycles, HITL
        onboarding_hours=4.0,
        expertise="intermediate",
    )

    # LangGraph
    evaluator.assess_framework(
        framework_name="LangGraph",
        lines_of_code=60,
        complexity=6.5,
        concepts=4,  # States, Nodes, Edges, Conditional routing
        onboarding_hours=6.0,
        expertise="intermediate",
    )

    # CrewAI
    evaluator.assess_framework(
        framework_name="CrewAI",
        lines_of_code=50,
        complexity=5.0,
        concepts=3,  # Agents, Tasks, Crew
        onboarding_hours=3.5,
        expertise="intermediate",
    )

    return evaluator


# Ease-of-use survey for human participants

USABILITY_SURVEY_QUESTIONS = [
    {
        "id": "setup_difficulty",
        "question": "How difficult was it to set up your first task with this framework?",
        "scale": "1 (very easy) to 10 (very difficult)",
        "dimension": UsabilityDimension.SETUP_COMPLEXITY,
    },
    {
        "id": "concept_clarity",
        "question": "How clear were the framework's core concepts?",
        "scale": "1 (very unclear) to 10 (very clear)",
        "dimension": UsabilityDimension.CONCEPTUAL_CLARITY,
    },
    {
        "id": "code_readability",
        "question": "How readable was the code you wrote?",
        "scale": "1 (very hard to read) to 10 (very readable)",
        "dimension": UsabilityDimension.CODE_READABILITY,
    },
    {
        "id": "debugging_ease",
        "question": "How easy was it to debug issues?",
        "scale": "1 (very difficult) to 10 (very easy)",
        "dimension": UsabilityDimension.DEBUGGING_EASE,
    },
    {
        "id": "documentation",
        "question": "How would you rate the documentation quality?",
        "scale": "1 (very poor) to 10 (excellent)",
        "dimension": UsabilityDimension.DOCUMENTATION_QUALITY,
    },
    {
        "id": "error_messages",
        "question": "How helpful were error messages?",
        "scale": "1 (not helpful) to 10 (very helpful)",
        "dimension": UsabilityDimension.ERROR_MESSAGES,
    },
    {
        "id": "learning_curve",
        "question": "How would you rate the learning curve?",
        "scale": "1 (very steep) to 10 (very gentle)",
        "dimension": UsabilityDimension.LEARNING_CURVE,
    },
]
