"""
Voxarah — Web Server (FastAPI)
Replaces the Tkinter GUI. All core/ and coaching/ logic untouched.
Run: uvicorn web_main:app --reload --port 8000
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import (BackgroundTasks, FastAPI, File, Form, HTTPException,
                     Request, UploadFile, WebSocket, WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))

from core.settings import SettingsManager
from core.analyzer import (AudioAnalyzer, build_cleaned_samples,
                            build_cleaned_wav, build_label_file)
from core.recorder import VoxRecorder
from core.ai_coach import AICoach
from core.history import save_session, load_history, build_record
from core.retake import find_retake_regions, retake_summary
from coaching.profiles import score_recording, get_all_profiles, get_profile_info
from coaching.characters import CHARACTER_DB

APP_VERSION     = "2.1"
# When frozen by PyInstaller, bundled data lives in sys._MEIPASS.
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
UPLOAD_DIR      = Path(tempfile.mkdtemp(prefix="voxarah_web_"))
DISCORD_WEBHOOK = (
    "https://discord.com/api/webhooks/1491454548714324209/"
    "tPAWiZ8A9KAee0dr_wo5zafUvTNdwF78qkUP0wZnMYacNgtUGMVX_-e0sBk3dYdXFqxI"
)


# ── State ─────────────────────────────────────────────────────────────────────

class TakeState:
    def __init__(self):
        self.path: Optional[str]    = None
        self.wav_path: Optional[str] = None
        self.results: Optional[dict] = None
        self.report: Optional[dict]  = None
        self.filename: str           = ""
        self.analyzing: bool         = False


class AppState:
    def __init__(self):
        self.settings  = SettingsManager()
        self.recorder  = VoxRecorder()
        self.ai_coach  = AICoach()

        # Editor
        self.results:    Optional[dict] = None
        self.wav_path:   Optional[str]  = None
        self.filename:   str            = ""
        self.analyzing:  bool           = False
        self.recording:  bool           = False
        self.rec_start:  float          = 0.0

        # Coaching cache (keyed by profile name)
        self.coaching_report: Optional[dict] = None
        self.coaching_profile: str           = ""

        # Compare
        self.takes: List[TakeState] = [TakeState(), TakeState(), TakeState()]

        # Status
        self.ai_online:  bool = False
        self.ffmpeg_path: Optional[str] = None
        self._find_ffmpeg()

    def _find_ffmpeg(self):
        local = BASE_DIR / "samples" / "ffmpeg.exe"
        if local.exists():
            self.ffmpeg_path = str(local)
        elif shutil.which("ffmpeg"):
            self.ffmpeg_path = "ffmpeg"


state = AppState()


# ── WebSocket broadcast ───────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        msg  = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _broadcast(data: dict):
    """Thread-safe broadcast from a non-async context."""
    if _event_loop:
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(data), _event_loop)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_wav(src: str) -> Optional[str]:
    p = Path(src)
    if p.suffix.lower() == ".wav":
        return src
    if not state.ffmpeg_path:
        return None
    out = UPLOAD_DIR / (p.stem + "_conv.wav")
    try:
        subprocess.run(
            [state.ffmpeg_path, "-y", "-i", str(p),
             "-ac", "1", "-ar", "44100", str(out)],
            capture_output=True, timeout=120, check=True
        )
        return str(out) if out.exists() else None
    except Exception:
        return None


def fmt_time(sec: float) -> str:
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:05.2f}"


def safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def serialize_results(r: dict) -> dict:
    """Strip numpy arrays and make JSON-safe. Does NOT include raw samples."""
    if not r:
        return {}

    def cv(v):
        if isinstance(v, (np.float32, np.float64, np.float16)):
            return float(v)
        if isinstance(v, (np.int32, np.int64, np.int16, np.uint8)):
            return int(v)
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    def cvd(d):
        if isinstance(d, dict):
            return {k: cv(v) for k, v in d.items()}
        if isinstance(d, list):
            return [cvd(x) for x in d]
        return cv(d)

    out = {}
    for k, v in r.items():
        if k == "samples":       # never send raw samples over network
            continue
        out[k] = cvd(v)
    return out


def build_flags(results: dict) -> list:
    """Assemble flag list with start_sample/end_sample for the JS waveform."""
    if not results:
        return []
    sr   = results.get("sample_rate", 44100)
    dur  = results.get("duration", 1.0)
    n    = int(dur * sr)
    fmap = {
        "long_pauses":  "pause",
        "stutters":     "stutter",
        "unclear":      "unclear",
        "breaths":      "breath",
        "mouth_noises": "mouth_noise",
    }
    flags = []
    for key, ftype in fmap.items():
        for f in results.get(key, []):
            flags.append({
                "type":         ftype,
                "start_sample": int(safe_float(f.get("start", 0)) * sr),
                "end_sample":   int(safe_float(f.get("end",   0)) * sr),
                "start":        safe_float(f.get("start", 0)),
                "end":          safe_float(f.get("end",   0)),
                "desc":         f.get("desc", ""),
            })
    return sorted(flags, key=lambda x: x["start"])


def samples_to_peaks(samples, n: int = 1500) -> list:
    """Downsample audio samples to n peak values for waveform display."""
    if samples is None or len(samples) == 0:
        return []
    step  = max(1, len(samples) // n)
    peaks = []
    for i in range(0, len(samples) - step + 1, step):
        chunk = samples[i: i + step]
        peaks.append(float(np.max(np.abs(chunk))))
    return peaks[:n]


def assemble_issues(results: dict) -> list:
    """Build the flat issues list for the table."""
    sev_map = {"stutter": 2, "unclear": 3, "pause": 1,
               "breath": 1, "mouth_noise": 2}
    rows = []
    for f in build_flags(results):
        rows.append({
            "type":     f["type"],
            "time":     fmt_time(f["start"]),
            "desc":     f["desc"] or f["type"].replace("_", " ").title(),
            "severity": sev_map.get(f["type"], 1),
        })
    return rows


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Voxarah", version=APP_VERSION)

# Allow Tauri webview (tauri://localhost) to call the API cross-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "https://tauri.localhost", "http://tauri.localhost", "http://localhost"],
    allow_origin_regex=r"https?://localhost(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.on_event("startup")
async def startup():
    global _event_loop
    _event_loop = asyncio.get_event_loop()
    state.ffmpeg_ok = state.ffmpeg_path is not None
    # Check AI now, then keep polling every 30s so the app goes live
    # automatically once the user starts Ollama — no restart needed.
    threading.Thread(target=_ai_poll_loop, daemon=True).start()


def _check_ai():
    online = state.ai_coach.check_status()
    prev   = state.ai_online
    state.ai_online = online
    if online != prev:   # only broadcast on change to avoid noise
        _broadcast({"type": "status",
                    "ai_online": online,
                    "ffmpeg_ok": state.ffmpeg_path is not None})
    return online


def _ai_poll_loop():
    import time
    _check_ai()          # immediate check at startup
    while True:
        time.sleep(30)   # re-check every 30 seconds
        _check_ai()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Lightweight liveness check used by the Tauri sidecar boot sequence."""
    return {"ok": True}


@app.post("/api/shutdown")
async def shutdown():
    """Gracefully stop the server (called by Tauri before window close)."""
    import signal, os
    os.kill(os.getpid(), signal.SIGTERM)
    return {"ok": True}


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "templates" / "index.html")


@app.get("/api/status")
async def get_status():
    return {
        "version":    APP_VERSION,
        "ai_online":  state.ai_online,
        "ffmpeg_ok":  state.ffmpeg_path is not None,
        "analyzing":  state.analyzing,
        "recording":  state.recording,
        "has_results": state.results is not None,
        "filename":   state.filename,
    }


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Convert if needed
    wav = ensure_wav(str(dest))
    if not wav:
        raise HTTPException(400, "Could not read or convert file. Install ffmpeg.")

    state.wav_path  = wav
    state.filename  = file.filename
    state.results   = None
    state.coaching_report = None

    size_mb = dest.stat().st_size / 1_048_576
    return {"filename": file.filename, "wav_path": wav, "size_mb": round(size_mb, 2)}


# ── Analysis ──────────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze(background_tasks: BackgroundTasks):
    if not state.wav_path or not Path(state.wav_path).exists():
        raise HTTPException(400, "No file loaded.")
    if state.analyzing:
        raise HTTPException(409, "Analysis already running.")

    state.analyzing = True
    background_tasks.add_task(_run_analysis)
    return {"status": "started"}


def _run_analysis():
    try:
        _broadcast({"type": "progress", "fraction": 0.0, "msg": "Starting analysis..."})
        analyzer = AudioAnalyzer(state.settings.analysis_settings())

        def prog(fraction, msg):
            _broadcast({"type": "progress", "fraction": fraction, "msg": msg})

        results = analyzer.analyze(state.wav_path, progress_callback=prog)
        state.results = results
        state.coaching_report = None

        ser = serialize_results(results)
        ser["flags"]  = build_flags(results)
        ser["issues"] = assemble_issues(results)
        ser["waveform_peaks"] = samples_to_peaks(results.get("samples"))

        _broadcast({"type": "analysis_done", "results": ser})
        _broadcast({"type": "progress", "fraction": 1.0, "msg": "Done"})

        # Auto-save history
        try:
            profile = state.settings.get("coaching_profile")
            report  = score_recording(results, profile)
            record  = build_record(state.filename, profile, report, results)
            save_session(record)
        except Exception:
            pass

    except Exception as e:
        _broadcast({"type": "error", "msg": str(e)})
    finally:
        state.analyzing = False
        _broadcast({"type": "analyzing", "active": False})


@app.get("/api/results")
async def get_results():
    if not state.results:
        return JSONResponse({"error": "No results"}, status_code=404)
    ser = serialize_results(state.results)
    ser["flags"]          = build_flags(state.results)
    ser["issues"]         = assemble_issues(state.results)
    ser["waveform_peaks"] = samples_to_peaks(state.results.get("samples"))
    return ser


# ── Audio serving ──────────────────────────────────────────────────────────────

@app.get("/api/audio/original")
async def audio_original():
    if not state.wav_path or not Path(state.wav_path).exists():
        raise HTTPException(404, "No audio loaded.")
    return FileResponse(state.wav_path, media_type="audio/wav")


@app.get("/api/audio/cleaned")
async def audio_cleaned():
    if not state.results:
        raise HTTPException(404, "No analysis results.")
    out = UPLOAD_DIR / "cleaned_preview.wav"
    samples, sr = build_cleaned_samples(state.results,
                                        state.settings.analysis_settings())
    from core.analyzer import write_wav_mono
    write_wav_mono(str(out), samples, sr)
    return FileResponse(str(out), media_type="audio/wav")


# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/api/export/wav")
async def export_wav():
    if not state.results:
        raise HTTPException(404, "No results.")
    out = UPLOAD_DIR / "export_cleaned.wav"
    build_cleaned_wav(state.results, state.settings.analysis_settings(), str(out))
    return FileResponse(str(out), media_type="audio/wav",
                        filename=f"cleaned_{state.filename or 'audio'}.wav")


@app.get("/api/export/labels")
async def export_labels():
    if not state.results:
        raise HTTPException(404, "No results.")
    content = build_label_file(state.results)
    return Response(content=content, media_type="text/plain",
                    headers={"Content-Disposition":
                             f'attachment; filename="labels_{state.filename}.txt"'})


# ── Recording ────────────────────────────────────────────────────────────────

@app.post("/api/record/start")
async def record_start():
    if state.recording:
        raise HTTPException(409, "Already recording.")
    if not state.recorder.available:
        raise HTTPException(503, "sounddevice not available.")
    ok = state.recorder.start()
    if not ok:
        raise HTTPException(500, "Failed to start recording.")
    state.recording = True
    state.rec_start = time.time()
    threading.Thread(target=_rec_timer_loop, daemon=True).start()
    return {"status": "recording"}


def _rec_timer_loop():
    while state.recording:
        elapsed = time.time() - state.rec_start
        _broadcast({"type": "rec_timer", "seconds": round(elapsed, 1)})
        time.sleep(0.25)


@app.post("/api/record/stop")
async def record_stop(background_tasks: BackgroundTasks):
    if not state.recording:
        raise HTTPException(409, "Not recording.")
    state.recording = False
    path = state.recorder.stop()
    if not path:
        raise HTTPException(500, "Recording failed.")
    state.wav_path = path
    state.filename = "recording.wav"
    state.results  = None
    return {"status": "stopped", "path": path, "filename": "recording.wav"}


# ── Settings ─────────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    return state.settings.as_dict()


@app.post("/api/settings")
async def save_settings(body: Dict[str, Any]):
    state.settings.set_many(body)
    state.settings.save()
    return {"status": "saved"}


@app.post("/api/settings/reset")
async def reset_settings():
    state.settings.reset_to_defaults()
    return state.settings.as_dict()


# ── Coaching ─────────────────────────────────────────────────────────────────

@app.get("/api/profiles")
async def get_profiles():
    result = []
    for name in get_all_profiles():
        info = get_profile_info(name)
        result.append({
            "name":        name,
            "description": info.get("description", ""),
            "emoji":       info.get("emoji", ""),
        })
    return result


@app.post("/api/coaching/score")
async def coaching_score(body: Dict[str, Any]):
    if not state.results:
        raise HTTPException(404, "No results.")
    profile = body.get("profile", state.settings.get("coaching_profile"))
    report  = score_recording(state.results, profile)
    state.coaching_report   = report
    state.coaching_profile  = profile

    # Retake guide
    suggestions = find_retake_regions(state.results, report)
    summary     = retake_summary(suggestions, report.get("overall", 0))

    return {
        "report":      report,
        "retake":      {"summary": summary, "suggestions": suggestions},
    }


@app.post("/api/coaching/ai")
async def coaching_ai(body: Dict[str, Any]):
    """Start AI coaching — streams tokens via WebSocket."""
    if not state.results:
        raise HTTPException(404, "No results.")
    if not state.ai_online:
        raise HTTPException(503, "AI offline. Start Ollama and it will connect automatically.")

    profile  = body.get("profile", state.coaching_profile or
                        state.settings.get("coaching_profile"))
    report       = state.coaching_report or score_recording(state.results, profile)
    feedback     = report.get("feedback", [])
    scores       = report.get("scores", {})
    raw_stats    = state.results.get("stats", {})
    pitch_stats  = state.results.get("pitch_stats", {})
    character_name = body.get("character_name")

    def on_token(t: str):
        _broadcast({"type": "ai_token", "token": t})

    def on_done(text: str):
        _broadcast({"type": "ai_done", "text": text})

    state.ai_coach.get_coaching(
        profile_name=profile,
        scores=scores,
        feedback=feedback,
        raw_stats=raw_stats,
        pitch_stats=pitch_stats,
        character_name=character_name,
        on_token=on_token,
        on_done=on_done,
    )
    return {"status": "started"}


@app.post("/api/coaching/ai/cancel")
async def coaching_ai_cancel():
    state.ai_coach.cancel()
    return {"status": "cancelled"}


@app.post("/api/coaching/ai/chat")
async def coaching_ai_chat(body: Dict[str, Any]):
    """Continue the coaching conversation with a follow-up message."""
    if not state.ai_online:
        raise HTTPException(503, "AI offline. Start Ollama and it will connect automatically.")

    messages  = body.get("messages", [])   # [{role, content}, ...]
    if not messages:
        raise HTTPException(400, "No messages provided.")

    def on_token(t: str):
        _broadcast({"type": "ai_chat_token", "token": t})

    def on_done(text: str):
        _broadcast({"type": "ai_chat_done", "text": text})

    state.ai_coach.chat(messages=messages, on_token=on_token, on_done=on_done)
    return {"status": "started"}


# ── Characters ────────────────────────────────────────────────────────────────

@app.get("/api/characters")
async def get_characters():
    result = {}
    for name, data in CHARACTER_DB.items():
        result[name] = {
            "category":     data.get("category", ""),
            "description":  data.get("description", ""),
            "difficulty":   data.get("difficulty", ""),
            "vocal_qualities": data.get("vocal_qualities", []),
            "pro_tips":     data.get("pro_tips", []),
            "example_pros": data.get("example_pros", []),
            "common_mistakes": data.get("common_mistakes", []),
        }
    return result


# ── History ───────────────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history():
    records = load_history()
    records.reverse()   # newest first
    return records


# ── Compare ───────────────────────────────────────────────────────────────────

@app.post("/api/compare/upload/{slot}")
async def compare_upload(slot: int, file: UploadFile = File(...)):
    if slot not in (0, 1, 2):
        raise HTTPException(400, "Slot must be 0, 1, or 2.")
    dest = UPLOAD_DIR / f"take_{slot}_{file.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    wav = ensure_wav(str(dest))
    if not wav:
        raise HTTPException(400, "Could not convert file.")
    t = state.takes[slot]
    t.path     = str(dest)
    t.wav_path = wav
    t.filename = file.filename
    t.results  = None
    t.report   = None
    return {"slot": slot, "filename": file.filename}


@app.post("/api/compare/analyze/{slot}")
async def compare_analyze(slot: int, background_tasks: BackgroundTasks,
                          profile: str = ""):
    if slot not in (0, 1, 2):
        raise HTTPException(400, "Bad slot.")
    t = state.takes[slot]
    if not t.wav_path:
        raise HTTPException(404, "No file in this slot.")
    if t.analyzing:
        raise HTTPException(409, "Already analyzing.")
    t.analyzing = True
    use_profile = profile or state.settings.get("coaching_profile")
    background_tasks.add_task(_compare_analyze, slot, use_profile)
    return {"status": "started", "slot": slot}


def _compare_analyze(slot: int, profile: str):
    t = state.takes[slot]
    try:
        _broadcast({"type": "compare_progress", "slot": slot,
                    "msg": "Analyzing..."})
        analyzer = AudioAnalyzer(state.settings.analysis_settings())
        results  = analyzer.analyze(t.wav_path)
        report   = score_recording(results, profile)
        t.results = results
        t.report  = report
        _broadcast({
            "type":   "compare_done",
            "slot":   slot,
            "report": report,
            "stats":  results.get("stats", {}),
            "pitch_rating": results.get("pitch_stats", {}).get("rating", "—"),
        })
    except Exception as e:
        _broadcast({"type": "compare_error", "slot": slot, "msg": str(e)})
    finally:
        t.analyzing = False


@app.delete("/api/compare/{slot}")
async def compare_clear(slot: int):
    if slot not in (0, 1, 2):
        raise HTTPException(400, "Bad slot.")
    state.takes[slot] = TakeState()
    return {"status": "cleared", "slot": slot}


@app.post("/api/compare/rescore")
async def compare_rescore(body: Dict[str, Any]):
    profile = body.get("profile", state.settings.get("coaching_profile"))
    results_out = []
    for i, t in enumerate(state.takes):
        if t.results:
            t.report = score_recording(t.results, profile)
            results_out.append({
                "slot":   i,
                "report": t.report,
                "stats":  t.results.get("stats", {}),
                "pitch_rating": t.results.get("pitch_stats", {}).get("rating", "—"),
            })
    return results_out


# ── Feedback ──────────────────────────────────────────────────────────────────

@app.post("/api/feedback")
async def send_feedback(body: Dict[str, Any], background_tasks: BackgroundTasks):
    msg = body.get("message", "").strip()
    if not msg:
        raise HTTPException(400, "Empty message.")
    background_tasks.add_task(_post_feedback, msg)
    return {"status": "queued"}


def _post_feedback(msg: str):
    try:
        payload = json.dumps({
            "embeds": [{
                "title":       "Voxarah User Feedback",
                "description": msg,
                "color":       0xF5C518,
                "footer":      {"text": f"Voxarah v{APP_VERSION} (Web)"},
            }]
        }).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send initial state
        await ws.send_text(json.dumps({
            "type":       "status",
            "ai_online":  state.ai_online,
            "ffmpeg_ok":  state.ffmpeg_path is not None,
            "version":    APP_VERSION,
        }))
        while True:
            # Keep alive — receive pings from client
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("VOXARAH_PORT", 47891))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
