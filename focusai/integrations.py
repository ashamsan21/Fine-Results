"""Ports for optional services and Raspberry Pi hardware."""

from typing import Protocol


class VoiceCoach(Protocol):
    def speak(self, message: str) -> None: ...


class HardwareController(Protocol):
    def show(self, line_one: str, line_two: str = "") -> None: ...
    def signal(self, event: str) -> None: ...


class SilentVoiceCoach:
    """Offline default; replace with an ElevenLabs implementation later."""

    def speak(self, message: str) -> None:
        del message


class NoOpHardwareController:
    """Laptop default; replace with a Raspberry Pi GPIO implementation later."""

    def show(self, line_one: str, line_two: str = "") -> None:
        del line_one, line_two

    def signal(self, event: str) -> None:
        del event
