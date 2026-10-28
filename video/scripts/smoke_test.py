#!/usr/bin/env python3
"""
Phase 0 Smoke Test for Vertex AI Veo, Gemini, and Image Generation.

Budget constraint: FAST tier (veo-3.1-fast-generate-001), 2 clips max (16s total).
Tests:
  1. Live model discovery in the configured GCP project, us-central1
  2. Anchor first-frame plate generation using gemini-2.5-flash-image
  3. Generating two 8s 9:16 clips from the identical anchor plate with different spoken lines
  4. Native audio generation (generate_audio=True) and lip-sync assessment
  5. Upload to GCS and output gs:// URIs + local files
"""

import os
import sys
import time
from pathlib import Path
from google import genai
from google.genai import types

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "weaware")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GCS_BUCKET = os.getenv("CLOUD_BUILD_BUCKET", f"{PROJECT_ID}_cloudbuild")

OUTPUT_DIR = Path("video/scratch")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_client() -> genai.Client:
    return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def discover_models(client: genai.Client):
    print("=" * 60)
    print("STEP 1: DISCOVERING ACTIVE MODELS IN", PROJECT_ID, LOCATION)
    print("=" * 60)
    
    models = list(client.models.list())
    veo_models = []
    gemini_flash_models = []
    gemini_pro_models = []
    image_models = []
    
    for m in models:
        name = m.name.replace("publishers/google/models/", "")
        if "veo" in name:
            veo_models.append(name)
        elif "flash-image" in name or "pro-image" in name:
            image_models.append(name)
        elif "gemini" in name and "flash" in name and "image" not in name and "tts" not in name and "transcribe" not in name:
            gemini_flash_models.append(name)
        elif "gemini" in name and "pro" in name and "image" not in name and "tts" not in name:
            gemini_pro_models.append(name)
            
    print("\n[VEO MODELS]")
    for v in sorted(veo_models):
        print(f"  - {v}")
        
    print("\n[GEMINI FLASH MODELS]")
    for gf in sorted(gemini_flash_models):
        print(f"  - {gf}")

    print("\n[GEMINI PRO MODELS]")
    for gp in sorted(gemini_pro_models):
        print(f"  - {gp}")

    print("\n[IMAGE GENERATION MODELS]")
    for im in sorted(image_models):
        print(f"  - {im}")
        
    return {
        "veo": veo_models,
        "flash": gemini_flash_models,
        "pro": gemini_pro_models,
        "image": image_models,
    }


def generate_anchor_plate(client: genai.Client) -> bytes:
    print("\n" + "=" * 60)
    print("STEP 2: GENERATING ANCHOR FIRST-FRAME PLATE")
    print("=" * 60)
    
    prompt = (
        "Professional headshot of a charismatic male late-night comedy news anchor in his late 30s, "
        "wearing a navy tailored suit jacket and light blue dress shirt, sitting behind a curved modern walnut anchor desk. "
        "Background features a late-night talk show studio with soft blue and amber neon accents, blurred city skyline, "
        "looking directly into camera with an engaging wry smile, vertical 9:16 composition, broadcast TV lighting."
    )
    
    image_model = "gemini-2.5-flash-image"
    print(f"Calling {image_model} with prompt: {prompt[:80]}...")
    
    resp = client.models.generate_content(
        model=image_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )
    
    image_bytes = None
    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            break
            
    if not image_bytes:
        raise RuntimeError("Failed to generate anchor plate image: no inline_data returned")
        
    plate_path = OUTPUT_DIR / "anchor_plate.png"
    plate_path.write_bytes(image_bytes)
    print(f"✓ Saved anchor plate to {plate_path} ({len(image_bytes)} bytes)")
    return image_bytes


def generate_clip(client: genai.Client, clip_num: int, anchor_bytes: bytes, spoken_line: str, action: str):
    print(f"\n--- Generating Clip {clip_num} (Veo 3.1 Fast, 8s, 9:16, Native Audio) ---")
    print(f"Spoken line: \"{spoken_line}\"")
    
    prompt = (
        f"Medium close-up shot of the news anchor at his desk. {action}. "
        f"He looks straight into the camera and speaks aloud clearly with broadcast comedic delivery: \"{spoken_line}\" "
        f"Late-night talk show studio ambiance, sharp broadcast lighting, synchronized speech, vertical 9:16."
    )
    
    first_frame = types.Image(image_bytes=anchor_bytes, mime_type="image/png")
    
    config = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        duration_seconds=8,
        person_generation="allow_adult",
        generate_audio=True,
    )
    
    model_id = "veo-3.1-fast-generate-001"
    print(f"Submitting long-running operation to {model_id}...")
    start_time = time.time()
    
    operation = client.models.generate_videos(
        model=model_id,
        prompt=prompt,
        image=first_frame,
        config=config,
    )
    
    print(f"Operation started: {operation.name}. Polling...")
    poll_count = 0
    while not operation.done:
        time.sleep(10)
        poll_count += 1
        operation = client.operations.get(operation)
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s elapsed, poll #{poll_count}] Operation status: done={operation.done}")
        
    if operation.error:
        raise RuntimeError(f"Veo generation failed: {operation.error}")
        
    generated_video = operation.response.generated_videos[0]
    local_path = OUTPUT_DIR / f"smoke_clip_{clip_num}.mp4"
    if generated_video.video.video_bytes:
        local_path.write_bytes(generated_video.video.video_bytes)
    else:
        generated_video.video.save(str(local_path))
    
    file_size = local_path.stat().st_size
    duration = time.time() - start_time
    print(f"✓ Clip {clip_num} downloaded: {local_path} ({file_size} bytes in {duration:.1f}s)")
    return local_path


def upload_to_gcs(local_path: Path, gcs_blob_name: str) -> str:
    import subprocess
    gcs_uri = f"gs://{GCS_BUCKET}/{gcs_blob_name}"
    cmd = ["gcloud", "storage", "cp", str(local_path), gcs_uri]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to upload to GCS: {res.stderr}")
    print(f"✓ Uploaded {local_path.name} to {gcs_uri}")
    return gcs_uri


def main():
    client = get_client()
    
    # 1. Discover models
    catalog = discover_models(client)
    
    # 2. Anchor plate
    plate_path = OUTPUT_DIR / "anchor_plate.png"
    if plate_path.exists():
        print(f"\nUsing existing anchor plate at {plate_path}")
        anchor_bytes = plate_path.read_bytes()
    else:
        anchor_bytes = generate_anchor_plate(client)
    
    # 3. Clip 1
    clip1_local = OUTPUT_DIR / "smoke_clip_1.mp4"
    if not clip1_local.exists() or clip1_local.stat().st_size == 0:
        line_1 = "Welcome back to WeAware Late Night. Today, researchers discovered that drinking coffee backwards makes you yesterday's problem. Good evening."
        action_1 = "He raises an eyebrow, gestures with a pen in hand, then looks directly into camera"
        clip1_local = generate_clip(client, 1, anchor_bytes, line_1, action_1)
    else:
        print(f"\nUsing existing Clip 1 at {clip1_local} ({clip1_local.stat().st_size} bytes)")
    clip1_gcs = upload_to_gcs(clip1_local, f"smoke_test/smoke_clip_1_{int(time.time())}.mp4")
    
    # 4. Clip 2 (~20 words, same anchor, different line)
    clip2_local = OUTPUT_DIR / "smoke_clip_2.mp4"
    if not clip2_local.exists() or clip2_local.stat().st_size == 0:
        line_2 = "Both Reuters and local officials confirmed the findings. Meanwhile, Wall Street is already shorting yesterday's decaf futures with great enthusiasm."
        action_2 = "He leans slightly forward on the desk with a wry grin, tapping his pen on paper"
        clip2_local = generate_clip(client, 2, anchor_bytes, line_2, action_2)
    else:
        print(f"\nUsing existing Clip 2 at {clip2_local} ({clip2_local.stat().st_size} bytes)")
    clip2_gcs = upload_to_gcs(clip2_local, f"smoke_test/smoke_clip_2_{int(time.time())}.mp4")
    
    print("\n" + "=" * 60)
    print("PHASE 0 SMOKE TEST COMPLETE")
    print("=" * 60)
    print(f"Clip 1 GCS URI: {clip1_gcs}")
    print(f"Clip 2 GCS URI: {clip2_gcs}")
    print(f"Local files: {clip1_local}, {clip2_local}")


if __name__ == "__main__":
    main()
