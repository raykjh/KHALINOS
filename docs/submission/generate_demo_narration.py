"""Generate the timed four-minute KHALINOS demo narration."""

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
    NarrationClip("01_prepared_brief", "00:00", "00:12", "This is KHALINOS. The brief is prepared, but no execution has started. I am reviewing Materials, Goal, SixSense, and the expected outcome."),
    NarrationClip("02_authorize", "00:12", "00:16", "Now I will authorize a real side-scrolling game build."),
    NarrationClip("03_ai_gap", "00:16", "00:29", "AI is no longer unfamiliar. But there is still a gap between talking with AI, coding with AI, and trusting several agents with real work."),
    NarrationClip("04_real_work", "00:29", "00:35", "In practice, people still watch, retry, and verify the result."),
    NarrationClip("05_architecture", "00:35", "00:53", "KHALINOS helps define the goal, acceptance criteria, and budget. After approval, each agent receives only the Capability Packs needed for this job, then moves through planning, production, runtime checks, and verification."),
    NarrationClip("06_cloud", "00:53", "01:08", "The actual work runs on Google Cloud Run. Firestore holds the live state, and Cloud Storage keeps the artifacts and verification evidence."),
    NarrationClip("07_visibility", "01:08", "01:28", "The moving horse, active agent, milestones, Gemini calls, receipts, and verifier show what is happening without requiring intervention at every step."),
    NarrationClip("08_trinity", "01:28", "01:55", "While the live job continues, this previously verified result is Trinity. The same fixed agent team used a different Capability Pack composition for top-down combat, profession progression, visible attacks, skills, and healing."),
    NarrationClip("09_browser", "01:55", "02:18", "KHALINOS is not limited to game profiles. This Browser profile used a separate Capability Pack composition to produce a launch triage board."),
    NarrationClip("10_human_judgment", "02:18", "02:38", "Human judgment remains for questions of taste and direction. KHALINOS takes on repeatable planning, production, testing, and bounded repair while the user keeps the decisions that matter."),
    NarrationClip("11_verification", "02:38", "03:03", "KHALINOS does not turn a failed task into a success story. It releases a result only after runtime checks pass and a role-separated verifier inside the system accepts the evidence."),
    NarrationClip("12_same_execution", "03:03", "03:20", "This is the same execution ID shown before the wait was removed. The result appears only because that execution reached PASS."),
    NarrationClip("13_fresh_result", "03:20", "03:50", "This is the result from the execution you just watched: a party moving, fighting automatically, and reaching its destination. Different outputs follow one rule: give agents only the capabilities they need, and accept completion only when the evidence agrees. KHALINOS turns repeated supervision into verified delivery."),
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
    wav_path = OUTPUT_DIR / "KHALINOS-demo-narration-4m.wav"
    mp3_path = OUTPUT_DIR / "KHALINOS-demo-narration-4m.mp3"
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"]
    for result in results:
        command.extend(("-i", str(OUTPUT_DIR / str(result["file"]))))
    delayed_inputs = []
    filters = ["anullsrc=r=24000:cl=mono:d=240[silence]"]
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
    manifest = {"voice": VOICE, "rate": RATE, "pitch": PITCH, "timeline_target_seconds": 240, "full_tracks": {"wav": wav_path.name, "wav_duration_seconds": round(wav_duration, 3), "mp3": mp3_path.name, "mp3_duration_seconds": round(MP3(mp3_path).info.length, 3)}, "clips": results}
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['name']}: {result['duration_seconds']:.3f}s / {result['slot_seconds']}s (headroom {result['headroom_seconds']:+.3f}s)")


if __name__ == "__main__":
    asyncio.run(main())
