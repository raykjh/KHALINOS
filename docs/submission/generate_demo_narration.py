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
    NarrationClip("01_prepared_brief", "00:00", "00:20", "For this demo, the brief is already prepared, but no execution has started. I will review Materials, Goal, the SixSense choice, and the Outcome Preview, then authorize a new live run."),
    NarrationClip("02_authorize", "00:20", "00:24", "Now I will authorize a real side-scrolling game build."),
    NarrationClip("03_problem", "00:24", "00:40", "AI is no longer new. But there is still a gap between chatting with AI, coding with AI, and trusting agents with real work. AI-made websites and games can make it seem as if someone simply said, Build this, and everything appeared."),
    NarrationClip("04_architecture", "00:40", "00:56", "Before execution, KHALINOS helps define the goal, acceptance criteria, and budget. After one authorization, each agent receives only the capabilities needed for this job, then continues through planning, building, running, and testing."),
    NarrationClip("05_cloud", "00:56", "01:10", "The actual work runs on Google Cloud Run. Firestore holds the live state, and Cloud Storage keeps artifacts and verification evidence."),
    NarrationClip("06_visibility", "01:10", "01:20", "I can still see which agent is active, what it is doing, and which milestone is complete."),
    NarrationClip("07_trinity", "01:20", "01:50", "While the new build continues, this previously verified result is Trinity. The same fixed agent team used a different Capability Pack composition for top-down combat, profession progression, attacks, skills, and healing."),
    NarrationClip("08_browser", "01:50", "02:10", "KHALINOS is not limited to game profiles. This Browser profile used a separate workflow to produce a launch triage board."),
    NarrationClip("09_verification", "02:10", "02:35", "KHALINOS does not turn a failed task into a success story. It releases a result only after runtime checks pass and a role-separated verifier inside the system accepts the evidence."),
    NarrationClip("10_rule", "02:40", "03:05", "It keeps the project on course and does not call it complete without evidence. Different outputs follow one rule: give agents only the capabilities they need, and accept completion only when the evidence agrees."),
    NarrationClip("11_burden", "03:10", "03:30", "In practice, people still make decisions, retry failures, and check whether results work. KHALINOS reduces that repeated supervision while keeping human judgment where it matters."),
    NarrationClip("12_delivery", "03:30", "03:40", "KHALINOS turns repeated supervision into verified delivery."),
    NarrationClip("13_fresh_result", "03:40", "03:55", "The new run has passed. This is the result from the execution you just watched: a party moving, fighting automatically, and reaching its destination."),
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
    filters.append("[silence]" + "".join(delayed_inputs) + f"amix=inputs={len(delayed_inputs)+1}:duration=first:dropout_transition=0:normalize=0[mix]")
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
