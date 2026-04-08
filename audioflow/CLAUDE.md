# Voxarah Project Knowledge

## Project Name
- **Voxarah** — voice production suite for voice actors

## UI
- Desktop application built with **Tkinter**
- Design inspired by **Lamborghini** styling
- Primary color palette: **matte black** with accent yellow **#F5C518**
- Yellow is a prominent theme and favorite color integrated throughout the UI

## Architecture
- `core/`
  - `analyzer.py`
  - `audacity_bridge.py`
  - `settings.py`
  - `ai_coach.py`
  - `voice.py`
- `coaching/`
  - `profiles.py`
  - `characters.py`
  - `measured_benchmarks.py`
- `ui/`
  - `app.py`
  - `coaching_panel.py`
  - `components.py`
  - `design.py`

## AI Coaching
- Local LLM feedback using **Ollama llama3.1:8b**
- Text-to-speech via **pyttsx3**
- Voice priority chain: Ava (Natural) → Jenny (Natural) → Aria (Natural) → Zira
- Ava Natural is already handled in `core/voice.py` — no work needed

## Built-in Recorder
- `core/recorder.py` — `VoxRecorder` class using **sounddevice** (PortAudio)
- Records at 44100 Hz mono, saves to a temp WAV, passes directly into the analysis pipeline
- UI: **OPEN FILE** | **● REC** buttons in editor left panel; timer + STOP shown while recording
- `sounddevice` must be installed: `pip install sounddevice`

## Stutter Detection
- Uses a **micro-silence cluster algorithm**
- Replaced the previous **energy similarity** approach

## Coaching Benchmarks
- All 6 profiles calibrated from real LibriVox public-domain audio (4 samples each)
- `scrape_profiles.py` automates download → feature extraction → range computation → file update
- `coaching/measured_benchmarks.py` holds the calibrated ranges; `profiles.py` overlays them at scoring time
- Re-run `python scrape_profiles.py` to refresh benchmarks (cached downloads skipped automatically)

| Profile | WPM range | Calibration sources |
|---|---|---|
| Narrator / Documentary | 102–173 | Art of War, Jane Eyre, Alice in Wonderland |
| Audiobook | 102–173 | Art of War, Jane Eyre, Alice in Wonderland |
| Calm / Soothing | 71–125 | Marcus Aurelius, Whitman, Dante, à Kempis |
| Energetic / Hype | 87–133 | Sherlock Holmes, Treasure Island, Time Machine, Monte Cristo |
| Commercial / Salesy | 93–147 | Acres of Diamonds, Art of Public Speaking, Carnegie |
| Character / Animation | 82–141 | A Christmas Carol (dramatic), Alice, Romeo & Juliet, Holmes |

**Known limitation:** Energetic/Hype and Commercial/Salesy are calibrated from LibriVox narrators
(steady readers, ~90–130 WPM) — not true hype/promo voice actors. Hardcoded targets in
`profiles.py` (155–210 WPM / 130–180 WPM) are more accurate for those styles. Consider
sourcing YouTube/podcast clips for a future re-calibration of those two profiles.

## TODO
- Enable before/after playback
- Add batch processing
- Re-calibrate Energetic/Hype and Commercial/Salesy from non-LibriVox hype/promo sources

## Platform and Dependencies
- Target runtime: **Python 3.14**
- Platform: **Windows**
- Note: **audioop** module is not available
- `ffmpeg` is automatically downloaded to `samples/` folder by `benchmark_build.py` for MP3 conversion
- `samples/` folder is created automatically by `benchmark_build.py`
