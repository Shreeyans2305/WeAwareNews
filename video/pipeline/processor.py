"""
Post-Production Processor: Uses FFmpeg to concatenate clips, normalize loudness
to -14 LUFS, burn in mobile-safe subtitles, add text-only lower-third source attribution,
extract thumbnail, and compile metadata.json.
"""

import os
import json
import logging
import subprocess
import textwrap
from pathlib import Path
from typing import List, Dict, Any, Optional

from video.config.settings import settings
from video.pipeline.scripter import ScriptOutput

logger = logging.getLogger("weaware-video.processor")


def generate_subtitles_file(script: ScriptOutput, output_srt: Path) -> Path:
    """
    Creates an SRT subtitle file from the clip dialogues with accurate timings.
    """
    current_time = 0.0
    srt_lines = []

    for idx, clip in enumerate(script.clips, start=1):
        start_t = current_time
        end_t = current_time + clip.duration_seconds

        def format_timestamp(sec: float) -> str:
            hrs = int(sec // 3600)
            mins = int((sec % 3600) // 60)
            secs = int(sec % 60)
            millis = int((sec - int(sec)) * 1000)
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

        start_str = format_timestamp(start_t)
        end_str = format_timestamp(end_t)

        dialogue = clip.dialogue.strip().strip('"').strip("'")
        srt_lines.append(f"{idx}\n{start_str} --> {end_str}\n{dialogue}\n")
        current_time = end_t

    output_srt.write_text("\n".join(srt_lines), encoding="utf-8")
    return output_srt


def _ass_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _caption_chunks(dialogue: str, width: int = 28, max_lines: int = 2) -> List[str]:
    """Split dialogue into readable ASS cues of at most two short lines."""
    words = dialogue.strip().strip('"').strip("'").split()
    chunks: List[str] = []
    current: List[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        wrapped = textwrap.wrap(candidate, width=width, break_long_words=False, break_on_hyphens=False)
        if current and len(wrapped) > max_lines:
            lines = textwrap.wrap(" ".join(current), width=width, break_long_words=False, break_on_hyphens=False)
            chunks.append(r"\N".join(lines[:max_lines]))
            current = [word]
        else:
            current.append(word)
    if current:
        lines = textwrap.wrap(" ".join(current), width=width, break_long_words=False, break_on_hyphens=False)
        chunks.append(r"\N".join(lines[:max_lines]))
    return chunks


def generate_ass_subtitles_file(
    script: ScriptOutput,
    output_ass: Path,
    clip_durations: Optional[List[float]] = None,
    crossfade_seconds: float = 0.125,
) -> Path:
    """Create 1080x1920 safe-zone captions with no background box."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,90,190,410,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: List[str] = []
    current_time = 0.0
    durations = clip_durations or [float(clip.duration_seconds) for clip in script.clips]
    for index, (clip, duration) in enumerate(zip(script.clips, durations)):
        chunks = _caption_chunks(clip.dialogue)
        if not chunks:
            continue
        visible_duration = duration - (crossfade_seconds if index < len(durations) - 1 else 0.0)
        chunk_duration = visible_duration / len(chunks)
        for chunk_index, caption in enumerate(chunks):
            start = current_time + chunk_index * chunk_duration
            end = current_time + (chunk_index + 1) * chunk_duration
            safe_caption = caption.replace("{", r"\{").replace("}", r"\}")
            events.append(
                f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Caption,,0,0,0,,{safe_caption}"
            )
        current_time += visible_duration
    output_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_ass


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def trim_clip_to_speech_end(clip_path: Path, speech_end_seconds: float, tail_seconds: float = 0.3) -> Path:
    """Trim to the detected final spoken word plus a short room-tone tail."""
    duration = _probe_duration(clip_path)
    trim_at = min(duration, max(0.5, speech_end_seconds + tail_seconds))
    if duration - trim_at < 0.05:
        return clip_path
    output_path = clip_path.with_name(f"{clip_path.stem}_trimmed{clip_path.suffix}")
    command = [
        "ffmpeg", "-y", "-i", str(clip_path), "-t", f"{trim_at:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Clip trim failed: {result.stderr[-1000:]}")
    return output_path


def process_video_and_metadata(
    clip_paths: List[Path],
    script: ScriptOutput,
    source_names: List[str],
    output_dir: Path,
    run_metadata: Dict[str, Any],
    mock_mode: bool = False,
) -> Dict[str, Path]:
    """
    Assembles final video, thumbnail, and metadata.
    Returns: {"video": final_mp4, "thumbnail": thumb_jpg, "metadata": meta_json}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    final_video = output_dir / "final.mp4"
    thumbnail = output_dir / "thumbnail.jpg"
    metadata_file = output_dir / "metadata.json"

    if mock_mode:
        logger.info("[MOCK MODE] Skipping FFmpeg execution. Generating mock artifacts.")
        final_video.write_bytes(b"MOCK_FINAL_MP4")
        thumbnail.write_bytes(b"MOCK_THUMBNAIL_JPG")
        metadata_file.write_text(json.dumps(run_metadata, indent=2))
        return {
            "video": final_video,
            "thumbnail": thumbnail,
            "metadata": metadata_file,
        }

    # 1. Measure the already speech-trimmed clips and prepare ASS captions.
    crossfade_seconds = 0.125
    clip_durations = [_probe_duration(path) for path in clip_paths]
    ass_file = output_dir / "captions.ass"
    generate_ass_subtitles_file(script, ass_file, clip_durations, crossfade_seconds)

    # 3. Source Lower-Third Text (Strictly Text, No publisher photos)
    sources_text = "Sources: " + " + ".join(source_names[:3])
    # Sanitize for ffmpeg drawtext filter
    escaped_sources = sources_text.replace(":", "\\:").replace("'", "\\'")

    # 2. Crossfade both video and audio to avoid abrupt presenter jumps and
    # preserve continuous room tone across boundaries.
    input_args: List[str] = []
    filter_parts: List[str] = []
    for index, path in enumerate(clip_paths):
        input_args.extend(["-i", str(path)])
        filter_parts.append(
            f"[{index}:v]scale=1080:1920:flags=lanczos:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{index}]"
        )
        filter_parts.append(f"[{index}:a]aresample=48000,asetpts=PTS-STARTPTS[a{index}]")

    video_label = "v0"
    audio_label = "a0"
    cumulative = clip_durations[0]
    for index in range(1, len(clip_paths)):
        offset = cumulative - crossfade_seconds * index
        next_video = f"vx{index}"
        next_audio = f"ax{index}"
        filter_parts.append(
            f"[{video_label}][v{index}]xfade=transition=fade:duration={crossfade_seconds}:offset={offset:.3f}[{next_video}]"
        )
        filter_parts.append(
            f"[{audio_label}][a{index}]acrossfade=d={crossfade_seconds}:c1=tri:c2=tri[{next_audio}]"
        )
        video_label = next_video
        audio_label = next_audio
        cumulative += clip_durations[index]

    escaped_ass = str(ass_file.resolve()).replace("'", r"\'").replace(":", r"\:")
    filter_parts.append(
        f"[{video_label}]subtitles='{escaped_ass}',"
        f"drawtext=text='WeAware News':x=90:y=90:fontsize=34:fontcolor=white:"
        f"borderw=2:bordercolor=black@0.8:shadowx=1:shadowy=1,"
        f"drawtext=text='AI-generated presenters':x=90:y=145:fontsize=26:fontcolor=white:"
        f"borderw=2:bordercolor=black@0.8:enable='between(t,0,3)',"
        f"drawtext=text='{escaped_sources}':x=90:y=185:fontsize=24:fontcolor=white:"
        f"borderw=2:bordercolor=black@0.8[vout]"
    )
    filter_parts.append(f"[{audio_label}]loudnorm=I=-14:LRA=11:TP=-1.5[aout]")

    cmd = [
        "ffmpeg", "-y", *input_args,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(final_video),
    ]

    logger.info("Executing FFmpeg encoding...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"FFmpeg encoding failed: {res.stderr}")
        raise RuntimeError(f"FFmpeg encoding failed: {res.stderr[-2000:]}")

    # 5. Extract Thumbnail
    thumb_cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:01.500",
        "-i", str(final_video),
        "-vframes", "1",
        "-q:v", "2",
        str(thumbnail),
    ]
    subprocess.run(thumb_cmd, capture_output=True)

    # 6. Save metadata.json
    metadata_file.write_text(json.dumps(run_metadata, indent=2))

    return {
        "video": final_video,
        "thumbnail": thumbnail,
        "metadata": metadata_file,
    }
