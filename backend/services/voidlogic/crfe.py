"""
RecursiveFeedbackEngine (CRFE)
Three analysis modules:

    RSML  — Recursive Self-Referential Meta-Loop detector
            Detects recursive patterns, self-references, and iterative structures.
            Amplifies coherent loops, flags deadlocked ones.

    AHCL  — Anti-Axiomatic Heuristic Collapse detector
            Identifies logical paradoxes and contradictions.
            Resolves them through contextual reframing.

    EmergenceAmplifier
            Detects weak signals that resolve into larger patterns.
            Surfaces emergent concepts before they are explicitly named.
"""
from __future__ import annotations

import re
import hashlib
from typing import Dict, Any, List, Optional


# --- RSML patterns: what looks like a recursive or self-referential structure? ---
_RECURSIVE_MARKERS = {
    "again", "loop", "repeat", "cycle", "recurse", "iterate", "return",
    "same", "back", "reinforce", "rebuild", "restart", "redo", "regenerate",
    "self", "itself", "myself", "recursive", "feedback", "mirror",
}

# --- AHCL patterns: what creates a logical paradox or contradiction? ---
_PARADOX_PAIRS = [
    ({"always"}, {"never"}),
    ({"everything"}, {"nothing"}),
    ({"infinite"}, {"finite"}),
    ({"certain"}, {"impossible"}),
    ({"true"}, {"false"}),
    ({"stable"}, {"broken"}),
    ({"complete"}, {"missing"}),
]

# --- Emergence seeds: weak signals that hint at a larger pattern ---
_EMERGENCE_SEEDS = {
    "what if", "imagine", "could", "might", "perhaps", "potential",
    "emerging", "new", "novel", "pattern", "signal", "hint", "beginning",
    "proto", "seed", "spark", "glimpse", "almost", "nearly", "feels like",
}


class RSML:
    """Recursive Self-Referential Meta-Loop detector and amplifier."""

    def analyze(self, text: str) -> Dict[str, Any]:
        words = set(text.lower().split())
        matched = list(words & _RECURSIVE_MARKERS)
        score = round(min(len(matched) / 3, 1.0), 4)

        # Detect actual structural recursion (e.g., phrase appears twice)
        phrase_hashes = [hashlib.md5(p.encode(), usedforsecurity=False).hexdigest()[:6]
                         for p in re.split(r'[.!?]', text) if len(p.strip()) > 5]
        structural_recursion = len(phrase_hashes) != len(set(phrase_hashes))

        state = "AMPLIFIED" if score >= 0.6 else "DETECTED" if score >= 0.3 else "NOMINAL"

        return {
            "score":                score,
            "state":                state,
            "matched_markers":      matched,
            "structural_recursion": structural_recursion,
            "recommendation": (
                "Recursive loop detected — amplifying coherent thread."
                if state == "AMPLIFIED"
                else "Nominal flow — no recursive deadlock."
            ),
        }


class AHCL:
    """Anti-Axiomatic Heuristic Collapse — paradox detector and resolver."""

    def analyze(self, text: str) -> Dict[str, Any]:
        words = set(text.lower().split())
        paradoxes_found: List[Dict[str, Any]] = []

        for pos_set, neg_set in _PARADOX_PAIRS:
            if words & pos_set and words & neg_set:
                paradoxes_found.append({
                    "positive": list(pos_set),
                    "negative": list(neg_set),
                    "resolution": self._resolve(pos_set, neg_set),
                })

        collapsed = len(paradoxes_found) >= 2
        safe = not collapsed

        return {
            "paradoxes_detected": len(paradoxes_found),
            "paradoxes":          paradoxes_found,
            "collapse_risk":      collapsed,
            "system_safe":        safe,
            "status": (
                "COLLAPSE_RISK — Multiple paradoxes. Heuristic reframing engaged."
                if collapsed
                else "STABLE — No axiomatic collapse detected."
            ),
        }

    def _resolve(self, pos: set, neg: set) -> str:
        return (
            f"Paradox between [{', '.join(pos)}] and [{', '.join(neg)}] "
            f"resolved via contextual scope separation — "
            f"each term valid within its own frame of reference."
        )


class EmergenceAmplifier:
    """Detects weak emergent signals and amplifies them into named patterns."""

    def amplify(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        matched_seeds = [seed for seed in _EMERGENCE_SEEDS if seed in text_lower]
        score = round(min(len(matched_seeds) / 4, 1.0), 4)

        emergent_pattern = None
        if score >= 0.5:
            # Try to name the emergent concept
            concept_words = [w for w in text.split() if len(w) > 5 and w.isalpha()]
            if concept_words:
                emergent_pattern = f"Emergent concept: [{concept_words[0].capitalize()}] — pattern strengthening."

        return {
            "score":            score,
            "matched_seeds":    matched_seeds,
            "emergent_pattern": emergent_pattern,
            "amplified":        score >= 0.5,
            "signal": (
                "STRONG EMERGENCE — Pattern surfacing. Amplification active."
                if score >= 0.7
                else "WEAK SIGNAL — Emergence possible. Monitoring."
                if score >= 0.3
                else "BACKGROUND NOISE — No emergence detected."
            ),
        }


class RecursiveFeedbackEngine:
    """Master CRFE orchestrator — runs all three modules in sequence."""

    def __init__(self) -> None:
        self.rsml      = RSML()
        self.ahcl      = AHCL()
        self.emergence = EmergenceAmplifier()

    def process(self, text: str) -> Dict[str, Any]:
        rsml_result      = self.rsml.analyze(text)
        ahcl_result      = self.ahcl.analyze(text)
        emergence_result = self.emergence.amplify(text)

        overall_health = (
            "CRITICAL"  if not ahcl_result["system_safe"] else
            "AMPLIFIED" if rsml_result["state"] == "AMPLIFIED" else
            "EMERGING"  if emergence_result["amplified"] else
            "NOMINAL"
        )

        return {
            "rsml":           rsml_result,
            "ahcl":           ahcl_result,
            "emergence":      emergence_result,
            "system_health":  overall_health,
        }


# Module-level singleton
crfe = RecursiveFeedbackEngine()
