"""Local study-session planning engine."""

from .models import RecallQuestion, StudyPlan, StudyStep


class LocalStudyPlanner:
    def build_plan(
        self, subject: str, goal: str, deadline: str, total_minutes: int, energy: str = "Okay"
    ) -> StudyPlan:
        subject = subject.strip()
        goal = goal.strip()
        deadline = deadline.strip() or "No deadline provided"
        energy = energy.strip() or "Okay"

        warmup = max(3, round(total_minutes * 0.1))
        recall = max(5, round(total_minutes * 0.2))
        practice = max(5, round(total_minutes * 0.3))
        learn = total_minutes - warmup - recall - practice
        if learn < 5:
            learn = 5
            practice = max(3, total_minutes - warmup - recall - learn)

        steps = (
            StudyStep(
                f"Unlock what you know about {subject}",
                warmup,
                f"- List three things you remember about {subject}.\n"
                "- Circle the idea you feel least sure about.\n"
                "- You are ready to move on when you can name one clear knowledge gap.",
            ),
            StudyStep(
                "Build the key idea step by step",
                learn,
                f"- Study the core ideas needed to {goal.rstrip('.').lower()}.\n"
                "- Pause after each idea and explain why it matters in your own words.\n"
                "- Move on when you can explain the main idea without copying.",
            ),
            StudyStep(
                "Challenge yourself with one example",
                practice,
                "- Choose one representative example.\n"
                "- Complete it without copying the solution.\n"
                "- If stuck, name the exact step that is unclear before using a hint.\n"
                "- Move on when you can justify each step.",
            ),
            StudyStep(
                "Prove what you can remember",
                recall,
                "- Close your notes.\n"
                "- Explain the central idea from memory.\n"
                "- Write one question you still need to answer.\n"
                "- Finish when you have an honest picture of what stuck.",
            ),
        )

        questions = (
            RecallQuestion(
                f"Explain the most important idea in {subject} from this session.",
                "Explain it as if teaching a classmate.",
            ),
            RecallQuestion(
                f"How would you apply what you learned to achieve this goal: {goal}?",
                "Give a concrete method, example, or sequence of steps.",
            ),
            RecallQuestion(
                "What was hardest, and what would you check in your notes?",
                "Naming uncertainty is useful—it guides your next study session.",
            ),
        )

        urgency = "before your deadline" if deadline != "No deadline provided" else "while the goal is current"
        rationale = (
            f"This directly targets your stated goal {urgency}. "
            f"The session is sized for your {energy.lower()} focus level and leaves time to prove what stuck."
        )
        objective = f"Explain and apply the key ideas needed to {goal.rstrip('.').lower()}."
        return StudyPlan(
            subject,
            goal,
            deadline,
            total_minutes,
            energy,
            rationale,
            objective,
            steps,
            questions,
            "No study materials were analyzed. This plan is based on the check-in information.",
            (
                "Use one worked example, then solve a similar problem without looking.",
                "Review this topic again within 24 hours using active recall.",
            ),
        )
