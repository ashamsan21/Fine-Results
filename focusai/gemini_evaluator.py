"""Gemini evaluation for typed answers and handwritten work."""

import json
import os
from typing import Optional

from .models import RecallResult, StudyPlan


class GeminiRecallEvaluator:
    def __init__(self, api_key: str, model: Optional[str] = None) -> None:
        self.api_key = api_key
        self.model = model or os.getenv("FOCUSAI_GEMINI_MODEL", "gemini-3.8-flash")

    def evaluate(self, plan: StudyPlan, answers: list, evidence: list) -> RecallResult:
        from google import genai
        from google.genai import types

        evidence_by_question = {
            item["question"]: item["files"] for item in evidence
        }
        contents = [
            f"""You are a careful study coach. Evaluate the student's active recall.
Subject: {plan.subject}
Goal: {plan.goal}
Objective: {plan.objective}

Use typed answers, voice recordings, and attached handwritten work together.
Transcribe spoken responses before evaluating them. Read equations, diagrams,
and reasoning. Award partial credit. Do not guess unclear audio or illegible content.
Give specific instructional feedback, not generic encouragement."""
        ]
        for number, question in enumerate(plan.questions, 1):
            typed_answer = answers[number - 1].strip() or "[No typed answer]"
            contents.append(
                f"Question {number}: {question.prompt}\nTyped answer: {typed_answer}"
            )
            for submitted_file in evidence_by_question.get(number, []):
                contents.append(
                    types.Part.from_bytes(
                        data=submitted_file.getvalue(),
                        mime_type=submitted_file.type,
                    )
                )

        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "answered": {"type": "integer", "minimum": 0},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "diagnosis": {"type": "string"},
                "recommended_minutes": {"type": "integer", "minimum": 5, "maximum": 30},
            },
            "required": ["score", "answered", "strengths", "next_steps", "diagnosis", "recommended_minutes"],
        }
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema,
            ),
        )
        data = json.loads(response.text)
        return RecallResult(
            score=max(0, min(100, int(data["score"]))),
            answered=max(0, min(len(plan.questions), int(data["answered"]))),
            total=len(plan.questions),
            strengths=tuple(data["strengths"]),
            next_steps=tuple(data["next_steps"]),
            diagnosis=str(data["diagnosis"]),
            recommended_minutes=max(5, min(30, int(data["recommended_minutes"]))),
        )
