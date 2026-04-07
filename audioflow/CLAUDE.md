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
- Primary TTS voice: **Microsoft Zira**
- Looking for **Ava Natural** voice support

## Audacity Integration
- Integration with **Audacity** using **mod-script-pipe** named pipes
- Allows automation and communication with Audacity from the app

## Stutter Detection
- Uses a **micro-silence cluster algorithm**
- Replaced the previous **energy similarity** approach

## Coaching Benchmarks
- Benchmarks calibrated from real **LibriVox narration samples**
- Calibrated profiles: **Narrator** / **Audiobook**
- Remaining profiles still needing calibration:
  - Calm
  - Energetic
  - Commercial
  - Character

## TODO
- Calibrate remaining 4 coaching profiles
- Add built-in recorder
- Enable before/after playback
- Add batch processing
- Create a Windows `.exe` build

## Platform and Dependencies
- Target runtime: **Python 3.14**
- Platform: **Windows**
- Note: **audioop** module is not available
- `ffmpeg` is automatically downloaded to `samples/` folder by `benchmark_build.py` for MP3 conversion
- `samples/` folder is created automatically by `benchmark_build.py`
