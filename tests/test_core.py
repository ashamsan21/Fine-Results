import unittest

from focusai.evaluator import LocalRecallEvaluator
from focusai.planner import LocalStudyPlanner


class FocusAITest(unittest.TestCase):
    def setUp(self):
        self.plan = LocalStudyPlanner().build_plan(
            "Biology", "Understand cell division", "Friday", 45
        )

    def test_plan_uses_requested_time(self):
        self.assertEqual(sum(step.minutes for step in self.plan.steps), 45)
        self.assertEqual(len(self.plan.questions), 3)
        self.assertIn("cell division", self.plan.objective.lower())

    def test_empty_answers_score_zero(self):
        result = LocalRecallEvaluator().evaluate(self.plan, ["", "", ""])
        self.assertEqual(result.score, 0)
        self.assertEqual(result.answered, 0)

    def test_detailed_answers_score_above_short_answers(self):
        evaluator = LocalRecallEvaluator()
        short = evaluator.evaluate(self.plan, ["cells", "", ""])
        detailed = evaluator.evaluate(
            self.plan,
            [
                "Cell division copies genetic material before one cell separates into two cells.",
                "I would first identify each phase and then explain what changes in the nucleus.",
                "The checkpoints were hardest, so I would review how they prevent copying errors.",
            ],
        )
        self.assertGreater(detailed.score, short.score)
        self.assertEqual(detailed.answered, 3)
        self.assertEqual(detailed.recommended_minutes, 10)


if __name__ == "__main__":
    unittest.main()
