"""Transparent local feedback based on answer completion and detail."""

import re

from .models import RecallResult, StudyPlan


class LocalRecallEvaluator:
    def evaluate(self, plan: StudyPlan, answers: list[str]) -> RecallResult:
        meaningful = []
        detail_points = 0
        for answer in answers:
            words = re.findall(r"[A-Za-z0-9']+", answer)
            if len(words) >= 5:
                meaningful.append(answer)
            detail_points += min(len(words), 40)

        answered = len(meaningful)
        completion = answered / len(plan.questions)
        detail = detail_points / (40 * len(plan.questions))
        score = round(min(100, (completion * 70) + (detail * 30)))

        strengths = []
        if answered == len(plan.questions):
            strengths.append("You completed every active-recall prompt.")
        elif answered:
            strengths.append("You captured at least one idea from memory.")
        if detail >= 0.6:
            strengths.append("Your answers included useful detail and explanation.")
        if not strengths:
            strengths.append("You reached the reflection step—now make your recall specific.")

        next_steps = []
        if answered < len(plan.questions):
            next_steps.append("Revisit unanswered prompts without looking at your notes first.")
        if detail < 0.6:
            next_steps.append("Add an example or a step-by-step explanation to each answer.")
        next_steps.append(f"Schedule a 10-minute review of {plan.subject} within 24 hours.")

        if score >= 80:
            diagnosis = "Your recall is detailed enough to move forward. A short spaced review should protect it from fading."
            recommended_minutes = 10
        elif score >= 50:
            diagnosis = "You have the main idea, but parts of the explanation are still fragile. One short practice block should close the gap."
            recommended_minutes = 8
        else:
            diagnosis = "The topic is not yet stable in memory. Revisit one core explanation, then try recall again without notes."
            recommended_minutes = 12

        return RecallResult(
            score,
            answered,
            len(plan.questions),
            tuple(strengths),
            tuple(next_steps),
            diagnosis,
            recommended_minutes,
        )
