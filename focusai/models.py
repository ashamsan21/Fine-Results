from dataclasses import dataclass


@dataclass(frozen=True)
class StudyStep:
    title: str
    minutes: int
    instruction: str


@dataclass(frozen=True)
class RecallQuestion:
    prompt: str
    hint: str


@dataclass(frozen=True)
class StudyPlan:
    subject: str
    goal: str
    deadline: str
    total_minutes: int
    energy: str
    rationale: str
    objective: str
    steps: tuple[StudyStep, ...]
    questions: tuple[RecallQuestion, ...]
    material_summary: str
    study_ideas: tuple[str, ...]


@dataclass(frozen=True)
class RecallResult:
    score: int
    answered: int
    total: int
    strengths: tuple[str, ...]
    next_steps: tuple[str, ...]
    diagnosis: str
    recommended_minutes: int
