"""Gemini voice transcription and extraction for the check-in form."""

import json
import os


def transcribe_audio(api_key: str, recording) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("FOCUSAI_GEMINI_MODEL", "gemini-3.8-flash"),
        contents=[
            "Transcribe this student response accurately. Return only the spoken words.",
            types.Part.from_bytes(
                data=recording.getvalue(),
                mime_type=recording.type,
            ),
        ],
    )
    return response.text.strip()


def transcribe_checkin(api_key: str, recordings: dict, typed_values: dict) -> dict:
    from google import genai
    from google.genai import types

    contents = [
        """Extract a student's check-in information from the typed values and voice
recordings. Transcribe faithfully. Typed text takes priority when present. Do not
invent missing information. Return an empty string for anything not provided."""
    ]
    for field in ("subject", "goal", "deadline"):
        contents.append(f"Field: {field}\nTyped value: {typed_values.get(field, '') or '[empty]'}")
        recording = recordings.get(field)
        if recording is not None:
            contents.append(
                types.Part.from_bytes(
                    data=recording.getvalue(),
                    mime_type=recording.type,
                )
            )

    schema = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "goal": {"type": "string"},
            "deadline": {"type": "string"},
        },
        "required": ["subject", "goal", "deadline"],
    }
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("FOCUSAI_GEMINI_MODEL", "gemini-3.8-flash"),
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
        ),
    )
    return json.loads(response.text)
