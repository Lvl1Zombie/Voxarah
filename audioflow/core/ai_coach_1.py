"""
Voxarah — AI Coach
Generates personalized voice coaching feedback using a local LLM (Ollama)
with a smart template fallback when Ollama isn't available.

Requires: Ollama running locally (ollama.com) with llama3.1:8b
Fallback: Template-based feedback using actual analysis data (no LLM needed)
"""

import json
import threading
from typing import Dict, Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError


# ── Ollama Configuration ──────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"
TIMEOUT = 60  # seconds


def ollama_available() -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        req = Request("http://localhost:11434/api/tags",
                      headers={"Content-Type": "application/json"})
        resp = urlopen(req, timeout=5)
        data = json.loads(resp.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        # Check for our model (with or without :latest tag)
        for m in models:
            if m.startswith("llama3.1"):
                return True
        return False
    except Exception:
        return False


def ollama_generate(prompt: str, system: str = "",
                    callback: Optional[Callable] = None) -> str:
    """
    Send a prompt to Ollama and return the response.
    If callback is provided, streams tokens to it as they arrive.
    Returns the full response text.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "num_predict": 800,
        }
    }
    if system:
        payload["system"] = system

    body = json.dumps(payload).encode("utf-8")
    req = Request(OLLAMA_URL, data=body,
                  headers={"Content-Type": "application/json"})

    full_text = []
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                token = chunk.get("response", "")
                if token:
                    full_text.append(token)
                    if callback:
                        callback(token)
                if chunk.get("done", False):
                    break
    except Exception as e:
        if not full_text:
            return f"[Ollama error: {e}]"

    return "".join(full_text)


# ── System Prompt ─────────────────────────────────────────────────────────────

COACH_SYSTEM = """You are Voxarah, an expert voice acting and vocal performance coach. You analyze recordings and give specific, actionable feedback.

Rules:
- Be direct and specific. Reference exact numbers from the analysis.
- Compare the user's metrics to the pro benchmarks provided.
- Give 2-3 concrete things to improve, ordered by impact.
- Keep it conversational — like a coach talking to a student in a studio session.
- Keep your total response under 150 words.
- Never use bullet points or markdown formatting. Write in natural paragraphs.
- End with one specific exercise they can do right now."""


def build_coaching_prompt(results: dict, profile_name: str,
                          profile_scores: dict, benchmarks: dict) -> str:
    """Build a detailed prompt with the user's analysis data."""
    stats = results.get("stats", {})
    scores = profile_scores.get("scores", {})
    overall = profile_scores.get("overall", 0)
    grade = profile_scores.get("grade", "?")

    # Find weakest dimensions
    weak = sorted(scores.items(), key=lambda x: x[1])[:3]
    strong = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:2]

    prompt = f"""Here's a voice recording analysis for the "{profile_name}" style:

OVERALL: {overall}/100 ({grade})

Dimension scores:
- Pacing: {scores.get('pause_ratio', '?')}/100
- Delivery (stutter-free): {scores.get('stutters', '?')}/100
- Pause length: {scores.get('pause_length', '?')}/100
- Energy consistency: {scores.get('consistency', '?')}/100
- Clarity: {scores.get('clarity', '?')}/100

Recording stats:
- Duration: {stats.get('duration', 0):.1f}s
- Pauses trimmed: {stats.get('pause_count', 0)}
- Stutters detected: {stats.get('stutter_count', 0)}
- Unclear sections: {stats.get('unclear_count', 0)}
- Time saved by trimming: {stats.get('time_saved', 0):.1f}s

Pro benchmarks for {profile_name}:
- Speech rate: {benchmarks.get('speech_rate_wpm', (0,0))} WPM
- Pause ratio: {benchmarks.get('pause_ratio', (0,0))}
- Energy consistency: {benchmarks.get('energy_consistency', (0,0))}
- Dynamic range: {benchmarks.get('dynamic_range_db', (0,0))} dB

Weakest areas: {', '.join(f'{k} ({v}/100)' for k, v in weak)}
Strongest areas: {', '.join(f'{k} ({v}/100)' for k, v in strong)}

Give specific coaching feedback for this recording. What should they focus on to improve?"""

    return prompt


# ── Character Coaching Prompt ─────────────────────────────────────────────────

def build_character_prompt(results: dict, character_name: str,
                           char_scores: dict, char_info: dict) -> str:
    """Build a prompt for character-specific coaching."""
    scores = char_scores.get("scores", {})
    overall = char_scores.get("overall", 0)
    grade = char_scores.get("grade", "?")
    stats = results.get("stats", {})

    weak = sorted(scores.items(), key=lambda x: x[1])[:3]
    desc = char_info.get("description", "")
    ref = char_info.get("reference_desc", "")
    pros = char_info.get("example_pros", [])

    prompt = f"""Analyze this voice recording for the "{character_name}" character voice:

Character: {character_name}
Description: {desc}
Reference sound: {ref}
Pro examples: {', '.join(pros[:3])}

OVERALL: {overall}/100 ({grade})

Dimension scores:
- Pause ratio: {scores.get('pause_ratio', '?')}/100
- Speech rate: {scores.get('speech_rate', '?')}/100
- Consistency: {scores.get('consistency', '?')}/100
- Dynamic range: {scores.get('dynamic_range', '?')}/100
- Clarity: {scores.get('clarity', '?')}/100
- Delivery: {scores.get('stutters', '?')}/100

Recording stats:
- Duration: {stats.get('duration', 0):.1f}s
- Stutters: {stats.get('stutter_count', 0)}
- Unclear: {stats.get('unclear_count', 0)}

Weakest areas: {', '.join(f'{k} ({v}/100)' for k, v in weak)}

Give specific coaching feedback for performing this character voice. Reference what the pros sound like and what this recording is missing."""

    return prompt


# ── Template Fallback ─────────────────────────────────────────────────────────

def _template_feedback(scores: dict, profile_name: str, stats: dict) -> str:
    """Generate feedback from templates when Ollama isn't available."""
    overall = scores.get("overall", 0)
    dims = scores.get("scores", {})
    feedback_parts = []

    # Opening
    if overall >= 80:
        feedback_parts.append(
            f"Solid performance for {profile_name}. You scored {overall} overall, "
            f"which puts you in professional territory.")
    elif overall >= 60:
        feedback_parts.append(
            f"Your {profile_name} read scored {overall} overall. "
            f"There's a clear foundation here, but a few areas need work.")
    else:
        feedback_parts.append(
            f"Your {profile_name} read scored {overall}. "
            f"Let's focus on the biggest gaps to get you moving up fast.")

    # Dimension-specific feedback
    dim_feedback = {
        "pause_ratio": {
            "low": "Your pacing feels rushed. Try adding deliberate pauses between sentences. "
                   "Count to two in your head at every period.",
            "mid": "Pacing is reasonable but could be more intentional. "
                   "Mark your script with breath marks where you want to pause.",
            "high": "Great pacing. Your pauses feel natural and well-placed."
        },
        "stutters": {
            "low": f"The analyzer flagged {stats.get('stutter_count', 0)} stutters. "
                   "Try recording shorter takes and splicing the best ones together.",
            "mid": "Delivery is mostly clean with minor hesitations. "
                   "Warm up with tongue twisters before your next session.",
            "high": "Clean delivery with no significant stutters."
        },
        "consistency": {
            "low": "Your energy level is inconsistent across the recording. "
                   "Try recording in shorter bursts and matching your energy at the start of each take.",
            "mid": "Energy consistency is moderate. Focus on maintaining the same intensity "
                   "from the first sentence to the last.",
            "high": "Excellent consistency. Your energy stays steady throughout."
        },
        "clarity": {
            "low": "Some sections are dropping too quiet. Project more and keep your distance "
                   "from the mic consistent. Check your recording levels.",
            "mid": "Clarity is decent but a few sections dip. "
                   "Make sure you're not turning your head away from the mic mid-sentence.",
            "high": "Crystal clear audio throughout. Nice mic technique."
        },
        "pause_length": {
            "low": "Your longest pauses are too long for this style. "
                   "Trim dead air to keep the listener engaged.",
            "mid": "Pause lengths are acceptable. A few could be tighter.",
            "high": "Pause lengths are right in the sweet spot for this style."
        }
    }

    # Add feedback for the two weakest dimensions
    sorted_dims = sorted(dims.items(), key=lambda x: x[1])
    for key, score in sorted_dims[:2]:
        if key in dim_feedback:
            if score < 50:
                level = "low"
            elif score < 75:
                level = "mid"
            else:
                level = "high"
            feedback_parts.append(dim_feedback[key][level])

    # Closing exercise
    exercises = [
        "Exercise: Read one paragraph aloud three times. First at half speed, then normal, then with exaggerated energy. Record all three and compare.",
        "Exercise: Pick a 30-second passage and record it five times back to back without stopping. Listen to take 1 vs take 5.",
        "Exercise: Record yourself reading with a pencil held horizontally between your teeth. It forces clearer articulation. Then record again without it.",
        "Exercise: Stand up, plant your feet, and record one clean paragraph. Standing changes your breath support and energy.",
    ]
    import random
    feedback_parts.append(random.choice(exercises))

    return "\n\n".join(feedback_parts)


# ── Main Coach Interface ──────────────────────────────────────────────────────

class AICoach:
    """
    Generates AI-powered coaching feedback.
    Uses Ollama when available, falls back to templates.
    """

    def __init__(self):
        self._ollama_ok = None  # cached check
        self._lock = threading.Lock()

    def check_ollama(self) -> bool:
        """Check and cache Ollama availability."""
        self._ollama_ok = ollama_available()
        return self._ollama_ok

    @property
    def using_ai(self) -> bool:
        """Whether we're using the LLM or falling back to templates."""
        if self._ollama_ok is None:
            self.check_ollama()
        return self._ollama_ok

    def get_style_feedback(self, results: dict, profile_name: str,
                           profile_scores: dict, benchmarks: dict,
                           stream_callback: Optional[Callable] = None) -> str:
        """
        Get coaching feedback for a style profile.
        If Ollama is available, uses AI. Otherwise uses templates.
        stream_callback receives tokens as they arrive (AI mode only).
        """
        if self.using_ai:
            prompt = build_coaching_prompt(
                results, profile_name, profile_scores, benchmarks)
            return ollama_generate(prompt, COACH_SYSTEM, stream_callback)
        else:
            return _template_feedback(
                profile_scores, profile_name, results.get("stats", {}))

    def get_character_feedback(self, results: dict, character_name: str,
                               char_scores: dict, char_info: dict,
                               stream_callback: Optional[Callable] = None) -> str:
        """Get coaching feedback for a character voice."""
        if self.using_ai:
            prompt = build_character_prompt(
                results, character_name, char_scores, char_info)
            return ollama_generate(prompt, COACH_SYSTEM, stream_callback)
        else:
            return _template_feedback(
                char_scores, character_name, results.get("stats", {}))

    def get_feedback_async(self, callback: Callable, error_callback: Callable,
                           stream_callback: Optional[Callable] = None,
                           **kwargs):
        """
        Run feedback generation in a background thread.
        callback(text) is called with the final result.
        error_callback(error_msg) is called on failure.
        stream_callback(token) receives streaming tokens.
        """
        def _run():
            try:
                if "profile_name" in kwargs:
                    text = self.get_style_feedback(
                        stream_callback=stream_callback, **kwargs)
                elif "character_name" in kwargs:
                    text = self.get_character_feedback(
                        stream_callback=stream_callback, **kwargs)
                else:
                    text = "No coaching context provided."
                callback(text)
            except Exception as e:
                error_callback(str(e))

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
