# Voxarah — Setup & Usage Guide

## What This App Does
Voxarah is a desktop tool that:
- Analyzes your voice recordings for long pauses, stutters, and unclear audio
- Scores your delivery against 6 professional voice style profiles
- Connects directly to Audacity and applies edits **live on screen** — you watch it happen
- Lets you fine-tune every detection parameter from a settings panel

---

## Step 1: Install Python (if you don't have it)
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. ✅ During install, check **"Add Python to PATH"**

---

## Step 2: Install Dependencies
Open a **Command Prompt** in this folder, then run:
```
pip install pyinstaller
```
That's the only dependency. Everything else (tkinter, wave, etc.) is built into Python.

---

## Step 3: Enable Audacity Scripting (one-time setup)
1. Open **Audacity**
2. Go to **Edit → Preferences → Modules**
3. Find **mod-script-pipe** and set it to **Enabled**
4. Click **OK**
5. **Fully close and reopen Audacity** — this is required

> ⚠️  Audacity must be open and have a project loaded before you click "Connect to Audacity" in the app.

---

## Step 4A: Run Directly (no .exe needed)
```
python main.py
```

---

## Step 4B: Build a Standalone .exe
```
python build.py
```
Your `.exe` will appear in the `dist/` folder as `Voxarah.exe`.  
Double-click it — no Python needed on the target machine.

---

## How to Use It

### Editor Tab
1. Click **Open Audio File** — supports WAV, MP3, M4A, OGG, FLAC
   - For MP3/M4A/OGG/FLAC: install **ffmpeg** and add it to PATH for automatic conversion
   - WAV files work with zero setup
2. Adjust **Max Pause** and **Silence Threshold** sliders
3. Click **Analyze Recording** — results appear in the table
4. Click **Apply Edits in Audacity** — watch your Audacity project update live

### Coaching Tab
1. Run analysis first
2. Pick a **Voice Style** from the dropdown
3. See your score across 5 dimensions + personalized feedback
4. Read the style-specific tips at the bottom

### Audacity Tab
- Click **Connect to Audacity** (Audacity must be open)
- Use direct controls: Play, Stop, Undo, Fit Window, etc.
- **Import Label File** — push all flags into Audacity's label track
- Watch the **Activity Log** to see every command sent

### Settings Tab
Every parameter the app uses is configurable here. Changes auto-save when you click **Save Settings**.

---

## FAQ

**Q: The app says "Cannot find Audacity pipe"**  
A: Make sure mod-script-pipe is enabled (see Step 3) AND Audacity is open with a project loaded.

**Q: MP3/M4A files don't load**  
A: Install ffmpeg: https://ffmpeg.org/download.html — add it to your system PATH.

**Q: Audacity edits are applying but the timing is off**  
A: Make sure Audacity has the correct audio file open (the same one you analyzed in Voxarah).

**Q: The .exe won't open (Windows SmartScreen warning)**  
A: Click "More info" → "Run anyway". This happens with unsigned executables.

---

## Voice Style Profiles

| Style | Best For | Target Pace |
|---|---|---|
| 🌙 Calm / Soothing | Meditation, ASMR, wellness | 100–140 WPM |
| ⚡ Energetic / Hype | Gaming, promos, hype reels | 160–210 WPM |
| 🎬 Narrator / Documentary | Nature docs, explainers | 130–160 WPM |
| 📣 Commercial / Salesy | Ads, demos, promos | 140–175 WPM |
| 🎭 Character / Animation | Cartoons, games | 120–190 WPM |
| 📚 Audiobook | Long-form narration | 140–170 WPM |

---

## File Structure
```
voxarah/
├── main.py              ← Run this
├── build.py             ← Build .exe
├── requirements.txt
├── core/
│   ├── analyzer.py      ← Audio analysis engine
│   ├── audacity_bridge.py ← Audacity scripting
│   └── settings.py      ← Settings persistence
├── coaching/
│   └── profiles.py      ← 6 voice style profiles + scoring
└── ui/
    └── app.py           ← Full Tkinter UI
```
