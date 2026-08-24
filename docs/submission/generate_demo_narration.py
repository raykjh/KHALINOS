"""Generate the timed 3:15 Trinity-first KHALINOS demo narration."""

from __future__ import annotations

import asyncio
import json
import subprocess
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from mutagen.mp3 import MP3

VOICE = "en-US-BrianMultilingualNeural"
RATE = "+0%"
PITCH = "+0Hz"
OUTPUT_DIR = Path(__file__).resolve().parent / "demo-audio"


@dataclass(frozen=True)
class NarrationClip:
    name: str
    start: str
    end: str
    text: str


CLIPS = (
    NarrationClip("01_working_result", "00:00", "00:07", "This is KHALINOS, and this is a verified game it produced."),
    NarrationClip("02_trinity_intake", "00:07", "00:31", "I begin with a bounded Trinity survival game. Materials define what is available. Goal states the playable outcome and evidence gates. SixSense keeps the human choice of visual direction. Preview makes the scope, exclusions, budget, and expected proof visible before any work starts."),
    NarrationClip("03_authorize_and_visibility", "00:31", "00:46", "After authorization, KHALINOS composes only the Capability Packs this profile needs. The active agent, milestones, receipts, Gemini calls, verifier, and execution ID make progress visible without constant supervision."),
    NarrationClip("04_architecture", "00:46", "01:06", "Gemini participates through Google ADK. A trusted host binds each agent to profile-specific capabilities. Deterministic runtime checks and a role-separated verifier examine the evidence, while repair is bounded instead of repeated blindly."),
    NarrationClip("05_cloud_proof", "01:06", "01:20", "The work runs on Google Cloud Run in this project and region. Firestore holds live state, Cloud Storage keeps artifacts and evidence, and the Worker Job carries the same execution ID shown in KHALINOS."),
    NarrationClip("06_same_execution_pass", "01:20", "01:35", "Only unchanged waiting was removed. This is the same Trinity execution ID. KHALINOS does not turn failure into a success story; delivery appears only after runtime checks and verification reach PASS."),
    NarrationClip("07_trinity_result", "01:35", "02:00", "Here is the result from that verified profile: a centered three-hero party on scrolling top-down terrain, with automatic attacks, visible skills, healing, enemy pressure, cooldowns, and progression. It is a bounded prototype, not a claim of commercial polish."),
    NarrationClip("08_side_scroll", "02:00", "02:25", "The same agent team can take a different composition. This Side-scroll profile plans horizontal travel, grounded movement, automatic combat, and a destination. Its separate Cloud execution reaches its own checks and produces a moving result."),
    NarrationClip("09_browser", "02:25", "02:50", "KHALINOS is not limited to games. This Browser profile selects another Capability Pack composition, runs as a separate Cloud execution, and delivers a verified Launch Triage Board rather than a Godot artifact."),
    NarrationClip("10_conclusion", "02:50", "03:15", "These outputs are different, but the rule stays the same: give agents only the capabilities they need, keep human judgment for direction, and accept completion only when runtime and verification evidence agree. KHALINOS takes on repeatable supervision and delivers bounded, verified results."),
)


def seconds(timestamp: str) -> int:
    minutes, seconds_value = timestamp.split(":", maxsplit=1)
    return int(minutes) * 60 + int(seconds_value)


async def generate(clip: NarrationClip) -> dict[str, object]:
    output_path = OUTPUT_DIR / f"{clip.name}.mp3"
    await edge_tts.Communicate(clip.text, voice=VOICE, rate=RATE, pitch=PITCH).save(str(output_path))
    duration = MP3(output_path).info.length
    slot_duration = seconds(clip.end) - seconds(clip.start)
    if duration > slot_duration:
        raise RuntimeError(f"{clip.name} exceeds its slot by {duration - slot_duration:.3f}s")
    return {**asdict(clip), "file": output_path.name, "duration_seconds": round(duration, 3), "slot_seconds": slot_duration, "headroom_seconds": round(slot_duration - duration, 3)}


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = [await generate(clip) for clip in CLIPS]
    wav_path = OUTPUT_DIR / "KHALINOS-demo-narration-3m15s.wav"
    mp3_path = OUTPUT_DIR / "KHALINOS-demo-narration-3m15s.mp3"
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"]
    for result in results:
        command.extend(("-i", str(OUTPUT_DIR / str(result["file"]))))
    delayed_inputs = []
    timeline_seconds = 195
    filters = [f"anullsrc=r=24000:cl=mono:d={timeline_seconds}[silence]"]
    for index, clip in enumerate(CLIPS):
        name = f"clip{index}"
        filters.append(f"[{index}:a]adelay={seconds(clip.start) * 1000}:all=1[{name}]")
        delayed_inputs.append(f"[{name}]")
    filters.append("[silence]" + "".join(delayed_inputs) + f"amix=inputs={len(delayed_inputs)+1}:duration=first:dropout_transition=0:normalize=0[mixed]")
    filters.append("[mixed]volume=4dB,alimiter=limit=0.95[mix]")
    filters.append("[mix]asplit=2[wav][mp3]")
    command.extend(("-filter_complex", ";".join(filters), "-map", "[wav]", "-c:a", "pcm_s16le", str(wav_path), "-map", "[mp3]", "-c:a", "libmp3lame", "-b:a", "192k", str(mp3_path)))
    subprocess.run(command, check=True)
    with wave.open(str(wav_path), "rb") as wav_file:
        wav_duration = wav_file.getnframes() / wav_file.getframerate()
    manifest = {"voice": VOICE, "rate": RATE, "pitch": PITCH, "timeline_target_seconds": timeline_seconds, "full_tracks": {"wav": wav_path.name, "wav_duration_seconds": round(wav_duration, 3), "mp3": mp3_path.name, "mp3_duration_seconds": round(MP3(mp3_path).info.length, 3)}, "clips": results}
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['name']}: {result['duration_seconds']:.3f}s / {result['slot_seconds']}s (headroom {result['headroom_seconds']:+.3f}s)")


if __name__ == "__main__":
    asyncio.run(main())
