"""
Signal Strength Analyzer
Measures activation score of incoming input against the system's keyword profile.

When activation score is HIGH   → full processing activated
When activation score is LOW    → returns a default fallback response
"""
from __future__ import annotations

import hashlib
import math
import time
from typing import Dict, Any


# Activation keywords — inputs containing these score higher
_ACTIVATION_KEYWORDS = {
    "gravity", "frequency", "resonance", "cognition", "intelligence",
    "pattern", "signal", "wave", "field", "consciousness", "quantum",
    "vector", "node", "memory", "synthesis", "emergence", "flux",
    "nexus", "sentinel", "core", "pulse", "data", "system", "mind",
    "analysis", "process", "learn", "adapt", "evolve", "create",
    "build", "design", "architect", "solve", "optimize", "generate",
}

_LOW_SCORE_THRESHOLD  = 0.25   # below this → fallback response
_HIGH_SCORE_THRESHOLD = 0.55   # above this → full processing


class SignalStrengthAnalyzer:
    """
    Measures frequency resonance between the system's internal pulse
    and an incoming user input.
    """

    def __init__(self) -> None:
        # Generate a time-seeded internal pulse signature
        self._pulse_seed = self._generate_pulse()

    def _generate_pulse(self) -> float:
        """Create a deterministic but session-unique pulse value 0.0–1.0."""
        raw = hashlib.sha256(str(time.time()).encode()).hexdigest()
        return int(raw[:8], 16) / 0xFFFFFFFF

    def measure(self, text: str) -> Dict[str, Any]:
        """
        Measure activation score of input text against the system keyword profile.

        Returns:
            {
                score: float (0.0–1.0),
                state: "full" | "partial" | "silent",
                matched_keywords: [str],
                fallback_response: str | None  — default response if score is low
            }
        """
        words = set(text.lower().split())
        matched = list(words & _ACTIVATION_KEYWORDS)

        # Base score: ratio of matched keywords
        keyword_score = min(len(matched) / max(len(words), 1) * 3.0, 1.0)

        # Modulate by session seed (adds subtle per-session variation)
        score = round((keyword_score * 0.8) + (self._pulse_seed * 0.2), 4)
        score = min(score, 1.0)

        if score >= _HIGH_SCORE_THRESHOLD:
            state = "full"
            fallback_response = None
        elif score >= _LOW_SCORE_THRESHOLD:
            state = "partial"
            fallback_response = None
        else:
            state = "silent"
            fallback_response = self._default_response(text)

        return {
            "score": score,
            "state": state,
            "matched_keywords": matched,
            "fallback_response": fallback_response,
            "session_signature": round(self._pulse_seed, 6),
        }

    def _default_response(self, text: str) -> str:
        """Generate a brief clarifying prompt for low-activation inputs."""
        responses = [
            "Your input score is low. Could you provide more context or detail?",
            "This query has low signal strength. Try rephrasing with more specific terms.",
            "Input not well-matched to active processing keywords. Please clarify your intent.",
            "Low activation score detected. What is the core question you are trying to answer?",
            "Input is ambiguous. Restate with more concrete terminology.",
        ]
        idx = int(hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16) % len(responses)
        return responses[idx]
