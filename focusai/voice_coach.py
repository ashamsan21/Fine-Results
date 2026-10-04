"""Optional ElevenLabs audio generation for timed focus coaching cues."""

import base64
import os


def generate_coaching_audio(messages: tuple) -> tuple:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return tuple()
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=api_key)
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    results = []
    for message in messages:
        response = client.text_to_speech.convert(
            text=message,
            voice_id=voice_id,
            model_id="eleven_flash_v2_5",
            output_format="mp3_22050_32",
        )
        results.append(base64.b64encode(b"".join(response)).decode("ascii"))
    return tuple(results)
