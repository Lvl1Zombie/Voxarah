# Voxarah — Voice Production Suite

A coaching tool for beginner voice actors. Record or load an audio file and get instant feedback on pacing, delivery, pitch, breaths, mouth noise, and more — scored against professional voice style profiles.

---

## Download

**[→ Download Voxarah.exe from the latest release](https://github.com/Lvl1Zombie/Voxarah/releases/latest)**

No installation required. Just download and run.

---

## What It Does

**Analyzes your recording for:**
- Stutters and unclear delivery
- Awkward pauses (too long, too short)
- Audible breaths and inhales
- Mouth noise (lip smacks, tongue clicks)
- Pitch variance — are you expressive or flat?
- Consistency and clarity throughout

**Coaches you with:**
- A score (0–100) and letter grade against your chosen voice profile
- Plain-English feedback explaining what happened and what to fix
- Style-specific tips for Narrator, Audiobook, Commercial, Character, and more
- Session history so you can track improvement over time

**Tools:**
- Built-in microphone recorder — no external software needed
- Before/after playback — hear the cleaned version vs. your original
- Multi-take comparison — load up to 3 takes and see which one wins
- Color-coded waveform with issue flags and pitch strip
- AI coaching via Ollama (optional — works without it)

---

## Quick Start

1. Download `Voxarah.exe` from the [releases page](https://github.com/Lvl1Zombie/Voxarah/releases/latest)
2. Double-click to launch — no install, no setup
3. Click **OPEN FILE** to load a WAV, MP3, or other audio file — or hit **● REC** to record directly
4. Click **ANALYZE**
5. Switch to the **COACHING** tab to see your score and feedback

---

## Voice Profiles

Choose the profile that matches what you're recording for:

| Profile | Best for |
|---|---|
| Narrator / Documentary | Steady, authoritative reads |
| Audiobook | Long-form, consistent pacing |
| Calm / Soothing | Meditation, ASMR, wellness |
| Energetic / Hype | Trailers, promos, hype reels |
| Commercial / Salesy | Ad copy, product demos |
| Character / Animation | Acting range, expressive delivery |

---

## Optional: AI Coach

Voxarah can give conversational, streamed coaching feedback using a local AI model.

1. Install [Ollama](https://ollama.com)
2. Run: `ollama pull llama3.1:8b`
3. The AI Coach section in the Coaching tab will show **AI LIVE** and become active

This is fully optional — the app works completely without it.

---

## Optional: MP3 / Non-WAV Support

Voxarah natively reads WAV files. To open MP3, M4A, FLAC, or OGG files, place `ffmpeg.exe` in the same folder as `Voxarah.exe`.

Download FFmpeg: [ffmpeg.org/download.html](https://ffmpeg.org/download.html)

---

## System Requirements

- Windows 10 or 11 (64-bit)
- Microphone (for recording)
- ~100MB disk space

---

## Changelog

See [What's New](https://github.com/Lvl1Zombie/Voxarah/releases) on the releases page, or open the app and go to **Settings → WHAT'S NEW**.
