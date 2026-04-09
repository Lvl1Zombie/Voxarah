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


def _build_prompt(profile_name, scores, feedback, character_name=None,
                  raw_stats=None, pitch_stats=None):
    """Build a coaching prompt from analysis results."""
    lines = []
    if character_name:
        lines.append(f"You are a world-class voice acting coach. The student just recorded a take "
                     f"for the character \"{character_name}\" (style: {profile_name}).")
    else:
        lines.append(f"You are a world-class voice acting coach. The student just recorded a take "
                     f"in the \"{profile_name}\" voice style.")

    lines.append(f"\nOverall score: {scores.get('overall', '?')}/100 "
                 f"(grade: {scores.get('grade', '?')})")
    lines.append("\nDimension scores (0-100):")

    dim_names = {
        'pause_ratio':   'Pacing / Pause Ratio',
        'stutters':      'Delivery / Stutters',
        'pause_length':  'Pause Length Control',
        'consistency':   'Energy Consistency',
        'clarity':       'Clarity / Intelligibility',
        'speech_rate':   'Speech Rate',
        'dynamic_range': 'Dynamic Range',
        'delivery':      'Delivery',
        'pacing':        'Pacing',
        'expression':    'Expression',
        'pauseControl':  'Pause Control',
    }
    for key, val in scores.get('scores', {}).items():
        lines.append(f"  - {dim_names.get(key, key)}: {val}")

    # Raw analyzer stats — concrete numbers for the AI to reason from
    if raw_stats:
        lines.append("\nRaw recording measurements:")
        wpm = raw_stats.get('wpm')
        if wpm:
            lines.append(f"  - Speech rate: {wpm:.0f} words per minute")
        pause_count = raw_stats.get('pause_count')
        if pause_count is not None:
            lines.append(f"  - Pauses detected: {pause_count}")
        time_saved = raw_stats.get('time_saved')
        if time_saved is not None:
            lines.append(f"  - Dead air removed: {time_saved:.1f} seconds")
        pause_ratio = raw_stats.get('pause_ratio')
        if pause_ratio is not None:
            lines.append(f"  - Pause ratio: {pause_ratio:.1%} of total recording")
        lines.append(f"  - Stutters: {raw_stats.get('stutter_count', 0)}")
        lines.append(f"  - Unclear sections: {raw_stats.get('unclear_count', 0)}")
        lines.append(f"  - Audible breaths: {raw_stats.get('breath_count', 0)}")
        lines.append(f"  - Mouth noises: {raw_stats.get('mouth_noise_count', 0)}")
        duration = raw_stats.get('duration') or raw_stats.get('total_duration')
        if duration:
            lines.append(f"  - Recording duration: {duration:.1f} seconds")

    if pitch_stats:
        lines.append("\nPitch analysis:")
        rating = pitch_stats.get('rating', '')
        if rating:
            lines.append(f"  - Pitch variation rating: {rating}")
        std_hz = pitch_stats.get('std_hz')
        if std_hz is not None:
            desc = 'expressive' if std_hz > 30 else 'moderate' if std_hz > 15 else 'flat/monotone'
            lines.append(f"  - Pitch standard deviation: {std_hz:.1f} Hz ({desc})")
        mean_hz = pitch_stats.get('mean_hz')
        if mean_hz is not None:
            lines.append(f"  - Average pitch: {mean_hz:.0f} Hz")

    if feedback:
        lines.append("\nDetected issues:")
        for dim, msg in feedback:
            lines.append(f"  - {dim}: {msg}")

    lines.append(
        "\nBased on these specific measurements, give actionable coaching advice in 4-6 sentences. "
        "Reference the actual numbers (WPM, stutter count, pitch variation etc.) when relevant. "
        "Be encouraging but direct. Focus on the 1-2 weakest areas. "
        "If the score is high, congratulate and suggest refinements."
    )
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
                     character_name=None, raw_stats=None, pitch_stats=None,
                     on_token=None, on_done=None):
        """
        Generate coaching advice. Streams tokens via on_token(str) callback.
        Calls on_done(full_text) when complete.
        Falls back to template if Ollama is offline.
        Runs in a background thread.
        """
        self._cancel.clear()

        def _run():
            prompt = _build_prompt(profile_name, scores, feedback,
                                   character_name, raw_stats, pitch_stats)

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

    def chat(self, messages, on_token=None, on_done=None):
        """
        Continue a conversation with the AI using a list of
        {role: 'user'|'assistant', content: str} messages.
        Streams via on_token, calls on_done when complete.
        """
        self._cancel.clear()

        def _run():
            if not self._online:
                text = "AI is offline. Start Ollama to continue the conversation."
                if on_token: on_token(text)
                if on_done:  on_done(text)
                return

            try:
                # Ollama /api/chat supports multi-turn messages natively
                body = json.dumps({
                    "model":    self.model,
                    "messages": messages,
                    "stream":   True,
                }).encode()

                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/chat",
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
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                full_text.append(token)
                                if on_token: on_token(token)
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

                if on_done: on_done("".join(full_text))

            except Exception as e:
                err = f"Chat error: {e}"
                if on_token: on_token(err)
                if on_done:  on_done(err)

        threading.Thread(target=_run, daemon=True).start()
