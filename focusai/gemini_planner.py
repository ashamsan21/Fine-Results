"""Gemini study-material analysis and adaptive session planning."""

import json
import os
import re
import time
import zipfile
from io import BytesIO

from .models import RecallQuestion, StudyPlan, StudyStep


STUDY_ANALYSIS_TEMPLATE = """
You are Focus Coach, an evidence-informed study coach. Analyze every uploaded
file together with the student's complete check-in. Do not ignore a file.

STUDENT CHECK-IN
- Subject: {subject}
- Goal: {goal}
- Deadline: {deadline}
- Maximum available time: {available_minutes} minutes
- Current focus level: {energy}

YOUR JOB
1. Summarize what the uploaded materials cover and identify the most important
   concepts, prerequisites, examples, likely misconceptions, and knowledge gaps.
2. Decide the best single learning objective for this session.
3. Recommend a realistic session duration no longer than the available time.
4. Create 3-5 ordered activities that alternate learning, thinking, applying,
   and retrieval. Activity minutes must add exactly to the recommended duration.
5. Create 3-5 short-answer retrieval questions grounded in the uploaded material.
6. Give specific additional study ideas the student can use after this session.

Be concrete and material-specific. Do not claim that a file contains something
unless it appears in that file. If a file is unclear, say so in the summary.

FOCUS-MODE STYLE
- Make every activity title specific, active, and encouraging. Never use generic
  titles such as "Prime your brain," "Understand," "Apply," or "Active recall."
- Each instruction must contain a short Markdown checklist of 2-4 observable
  actions beginning with "- ". Tell the student exactly what to read, explain,
  solve, compare, draw, or recall.
- Keep the challenge achievable and use supportive language without empty praise.
- End each activity with a clear success condition so the student knows when to
  move on.
""".strip()


def _docx_text(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    return re.sub(r"<[^>]+>", " ", xml).replace("&amp;", "&")


class GeminiStudyPlanner:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.model = os.getenv("FOCUSAI_GEMINI_MODEL", "gemini-3.8-flash")

    def build_plan(self, subject, goal, deadline, available_minutes, energy, files) -> StudyPlan:
        from google import genai
        from google.genai import types

        deadline = deadline.strip() or "No deadline provided"
        contents = [
            STUDY_ANALYSIS_TEMPLATE.format(
                subject=subject,
                goal=goal,
                deadline=deadline,
                available_minutes=available_minutes,
                energy=energy,
            )
        ]
        if not files:
            contents.append("No files were uploaded. Base the plan on the check-in only.")
        for uploaded_file in files:
            data = uploaded_file.getvalue()
            contents.append(f"Uploaded file: {uploaded_file.name}")
            if uploaded_file.name.lower().endswith(".docx"):
                contents.append(_docx_text(data))
            elif uploaded_file.type.startswith("text/") or uploaded_file.name.lower().endswith((".txt", ".md")):
                contents.append(data.decode("utf-8", errors="replace"))
            else:
                contents.append(types.Part.from_bytes(data=data, mime_type=uploaded_file.type))

        schema = {
            "type": "object",
            "properties": {
                "recommended_minutes": {"type": "integer", "minimum": 15},
                "rationale": {"type": "string"},
                "objective": {"type": "string"},
                "material_summary": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "object", "properties": {
                    "title": {"type": "string"}, "minutes": {"type": "integer"},
                    "instruction": {"type": "string"}}, "required": ["title", "minutes", "instruction"]}},
                "questions": {"type": "array", "items": {"type": "object", "properties": {
                    "prompt": {"type": "string"}, "hint": {"type": "string"}},
                    "required": ["prompt", "hint"]}},
                "study_ideas": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["recommended_minutes", "rationale", "objective", "material_summary", "steps", "questions", "study_ideas"],
        }
        client = genai.Client(api_key=self.api_key)
        response = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", response_json_schema=schema
                    ),
                )
                break
            except Exception as error:
                if attempt == 2 or "503" not in str(error):
                    raise
                time.sleep(attempt + 1)
        if response is None:
            raise RuntimeError("Gemini did not return a study plan.")
        data = json.loads(response.text)
        minutes = min(available_minutes, max(15, int(data["recommended_minutes"])))
        steps = tuple(StudyStep(item["title"], int(item["minutes"]), item["instruction"]) for item in data["steps"])
        if sum(step.minutes for step in steps) != minutes:
            difference = minutes - sum(step.minutes for step in steps)
            last = steps[-1]
            steps = steps[:-1] + (StudyStep(last.title, max(1, last.minutes + difference), last.instruction),)
        questions = tuple(RecallQuestion(item["prompt"], item["hint"]) for item in data["questions"])
        return StudyPlan(
            subject.strip(), goal.strip(), deadline, minutes, energy, data["rationale"],
            data["objective"], steps, questions, data["material_summary"], tuple(data["study_ideas"])
        )
