"""
Post-Production Processor: Uses FFmpeg to concatenate clips, normalize loudness
to -14 LUFS, burn in mobile-safe subtitles, add text-only lower-third source attribution,
extract thumbnail, and compile metadata.json.
"""

import os
import json
import logging
import subprocess
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

    # 1. Prepare Concat List
    concat_list = output_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")

    # 2. Prepare Subtitles
    srt_file = output_dir / "captions.srt"
    generate_subtitles_file(script, srt_file)

    # 3. Source Lower-Third Text (Strictly Text, No publisher photos)
    sources_text = "Sources: " + " + ".join(source_names[:3])
    # Sanitize for ffmpeg drawtext filter
    escaped_sources = sources_text.replace(":", "\\:").replace("'", "\\'")

    # 4. FFmpeg Command
    # Filters:
    # - loudnorm (normalize loudness to -14 LUFS)
    if getattr(settings, "final_output_1080p", True):
        scale_filter = "scale=1080:1920:flags=lanczos:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        drawtext_filter = (
            f"drawtext=text='{escaped_sources}':x=(w-text_w)/2:y=h-240:"
            f"fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10"
        )
        subtitles_filter = f"subtitles={srt_file.resolve()}:force_style='FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=160'"
    else:
        scale_filter = "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2"
        drawtext_filter = (
            f"drawtext=text='{escaped_sources}':x=(w-text_w)/2:y=h-160:"
            f"fontsize=20:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=8"
        )
        subtitles_filter = f"subtitles={srt_file.resolve()}:force_style='FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=110'"

    vf_filters = f"{scale_filter},{drawtext_filter},{subtitles_filter}"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-vf", vf_filters,
        "-af", "loudnorm=I=-14:LRA=11:TP=-1.5",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        str(final_video),
    ]

    logger.info("Executing FFmpeg encoding...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"FFmpeg encoding failed: {res.stderr}")
        # Fallback simpler concatenation if filters fail (e.g. font not found)
        fallback_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(final_video),
        ]
        subprocess.run(fallback_cmd, check=True)

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
