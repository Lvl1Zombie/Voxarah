"""
Voxarah — AI Coaching Engine
Ollama LLM integration with template fallback for offline use.
"""

import json
import threading
import urllib.request
import urllib.error


OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"


def _build_prompt(profile_name, scores, feedback, character_name=None):
    """Build a coaching prompt from analysis results."""
    lines = []
    if character_name:
        lines.append(f"You are a voice acting coach. The student just recorded a take "
                     f"for the character \"{character_name}\" (style: {profile_name}).")
    else:
        lines.append(f"You are a voice acting coach. The student just recorded a take "
                     f"in the \"{profile_name}\" voice style.")

    lines.append(f"\nOverall score: {scores.get('overall', '?')}/100 "
                 f"(grade: {scores.get('grade', '?')})")
    lines.append("\nDimension scores (0-100):")

    dim_names = {
        'pause_ratio': 'Pacing / Pause Ratio',
        'stutters': 'Delivery / Stutters',
        'pause_length': 'Pause Length Control',
        'consistency': 'Energy Consistency',
        'clarity': 'Clarity / Intelligibility',
        'speech_rate': 'Speech Rate',
        'dynamic_range': 'Dynamic Range',
    }
    for key, val in scores.get('scores', {}).items():
        label = dim_names.get(key, key)
        lines.append(f"  - {label}: {val}")

    if feedback:
        lines.append("\nDetected issues:")
        for dim, msg in feedback:
            lines.append(f"  - {dim}: {msg}")

    lines.append("\nGive specific, actionable coaching advice in 3-5 sentences. "
                 "Be encouraging but direct. Focus on the weakest dimensions. "
                 "If the score is high, congratulate and suggest refinements.")
    return "\n".join(lines)


def _template_response(profile_name, scores, feedback, character_name=None):
    """Generate a template coaching response when Ollama is offline."""
    overall = scores.get('overall', 0)
    grade = scores.get('grade', 'F')
    dim_scores = scores.get('scores', {})

    # Find weakest dimensions
    weak = sorted(dim_scores.items(), key=lambda x: x[1])[:2]
    strong = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)[:1]

    dim_labels = {
        'pause_ratio': 'pacing', 'stutters': 'delivery smoothness',
        'pause_length': 'pause control', 'consistency': 'energy consistency',
        'clarity': 'clarity', 'speech_rate': 'speech rate',
        'dynamic_range': 'dynamic range',
    }

    who = f'"{character_name}"' if character_name else f'the {profile_name} style'
    lines = []

    if overall >= 85:
        lines.append(f"Excellent work on {who}! Your overall score of {overall} ({grade}) "
                     f"shows strong command of this style.")
    elif overall >= 70:
        lines.append(f"Good take on {who}. Your score of {overall} ({grade}) shows solid "
                     f"fundamentals with room to refine.")
    elif overall >= 55:
        lines.append(f"Decent attempt at {who}. Your score of {overall} ({grade}) suggests "
                     f"you're on the right track but need focused practice.")
    else:
        lines.append(f"This take on {who} scored {overall} ({grade}). Don't be discouraged — "
                     f"targeted practice on the areas below will bring quick improvement.")

    if strong:
        k, v = strong[0]
        lines.append(f"Your strongest area is {dim_labels.get(k, k)} at {v}/100 — keep that up.")

    for k, v in weak:
        label = dim_labels.get(k, k)
        if v < 50:
            lines.append(f"Focus on {label} (scored {v}) — this is holding your overall grade back.")
        elif v < 70:
            lines.append(f"Your {label} ({v}) could use attention — small improvements here will bump your grade.")

    if feedback:
        _, msg = feedback[0]
        lines.append(f"Specific note: {msg}")

    lines.append("Record a short 30-second practice take focusing just on the weakest "
                 "dimension, then re-analyze to track your progress.")

    return "\n\n".join(lines)


class AICoach:
    """Ollama-backed AI coaching with template fallback."""

    def __init__(self, model=None):
        self.model = model or DEFAULT_MODEL
        self._online = False
        self._cancel = threading.Event()

    def check_status(self):
        """Check if Ollama is reachable. Returns True/False."""
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read())
                models = [m['name'] for m in data.get('models', [])]
                self._online = len(models) > 0
                return self._online
        except Exception:
            self._online = False
            return False

    @property
    def is_online(self):
        return self._online

    def cancel(self):
        """Cancel any in-progress generation."""
        self._cancel.set()

    def get_coaching(self, profile_name, scores, feedback,
                     character_name=None, on_token=None, on_done=None):
        """
        Generate coaching advice. Streams tokens via on_token(str) callback.
        Calls on_done(full_text) when complete.
        Falls back to template if Ollama is offline.
        Runs in a background thread.
        """
        self._cancel.clear()

        def _run():
            prompt = _build_prompt(profile_name, scores, feedback, character_name)

            if not self._online:
                # Template fallback
                text = _template_response(profile_name, scores, feedback, character_name)
                if on_token:
                    on_token(text)
                if on_done:
                    on_done(text)
                return

            # Try Ollama streaming
            try:
                body = json.dumps({
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,
                }).encode()

                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/generate",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                full_text = []
                with urllib.request.urlopen(req, timeout=120) as resp:
                    for line in resp:
                        if self._cancel.is_set():
                            break
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                full_text.append(token)
                                if on_token:
                                    on_token(token)
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

                if on_done:
                    on_done("".join(full_text))

            except Exception:
                # Fallback to template on any error
                text = _template_response(profile_name, scores, feedback, character_name)
                if on_token:
                    on_token(text)
                if on_done:
                    on_done(text)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
