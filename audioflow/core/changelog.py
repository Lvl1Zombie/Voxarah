"""
Voxarah — Changelog
Add a new entry here whenever a version ships. Most recent version first.
Each entry: version, date, and a list of (title, description) feature tuples.
"""

CHANGELOG = [
    {
        "version": "2.1",
        "date": "April 2026",
        "features": [
            (
                "Multi-Take Comparison",
                "Load up to 3 recordings of the same script and compare them "
                "side-by-side. See which take wins per dimension, which has fewer "
                "issues, and get a plain-English summary of your best attempt."
            ),
            (
                "Patch Notes",
                "You're reading them. Version history now shows inside the app "
                "so you always know what changed after an update."
            ),
        ],
    },
    {
        "version": "2.0",
        "date": "April 2026",
        "features": [
            (
                "Session History & Progress Tracking",
                "Every analysis is saved automatically. The History tab shows a "
                "scrollable session list, an overall score trend chart, and "
                "per-dimension sparklines so you can see improvement over time."
            ),
            (
                "Pitch Visualization",
                "A color-coded pitch strip sits below the waveform — green for "
                "expressive variance, yellow for moderate, red for flat. A live "
                "playhead tracks your position during playback."
            ),
            (
                "Coaching Score Explanations",
                "Scores now come with plain-English coaching feedback: what "
                "happened, why it matters, and exactly what to do differently "
                "next time. Tips are tailored to your chosen voice profile."
            ),
            (
                "Breath & Mouth Noise Detection",
                "Two new issue categories: audible inhales and lip/tongue clicks. "
                "Both are flagged on the waveform, counted in the stats bar, and "
                "attenuated (not silenced) in the Edited playback."
            ),
            (
                "Before / After Playback",
                "Three playback buttons — Original, Edited, and Stop — let you "
                "hear exactly what was cleaned up. Edited audio applies smooth "
                "attenuation to breaths, mouth noises, and long pauses."
            ),
            (
                "Built-in Recorder",
                "Record directly from your microphone inside the app. No need to "
                "open a separate program — hit REC, speak, hit STOP, and the "
                "recording flows straight into analysis."
            ),
        ],
    },
    {
        "version": "1.0",
        "date": "March 2026",
        "features": [
            (
                "Voice Analysis Engine",
                "Detects pauses, stutters, and unclear audio using numpy-only "
                "signal processing. No heavy dependencies — runs on any Windows machine."
            ),
            (
                "6 Voice Coaching Profiles",
                "Score your delivery against Narrator, Audiobook, Calm/Soothing, "
                "Energetic/Hype, Commercial/Salesy, and Character/Animation profiles. "
                "Each profile has calibrated benchmarks from real LibriVox recordings."
            ),
            (
                "Character Coaching Panels",
                "Detailed coaching for specific character archetypes with difficulty "
                "ratings, pro references, technique tips, and common mistakes."
            ),
            (
                "AI Coach Integration",
                "Optional Ollama-powered AI coach gives streamed, conversational "
                "feedback on your recording. Includes text-to-speech voice output."
            ),
            (
                "Waveform Viewer",
                "Visual waveform with color-coded issue flags — yellow for pauses, "
                "red for stutters, cyan for breaths, orange for mouth noise."
            ),
            (
                "Settings Panel",
                "Fine-tune every detection threshold: silence level, pause duration, "
                "stutter window, and per-issue-type toggles."
            ),
        ],
    },
]
