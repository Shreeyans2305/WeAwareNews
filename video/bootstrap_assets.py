#!/usr/bin/env python3
"""
bootstrap_assets.py - One-off generator for late-night studio set & anchor plates.

Safety guarantee:
  Will NOT call Vertex AI or write to GCS without the explicit --confirm flag.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types
import yaml

from video.config.settings import settings

ASSETS_DIR = Path("video/assets")


def load_anchors_config() -> Dict[str, Any]:
    config_path = Path("video/config/anchors.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def generate_image_with_modalities(client: genai.Client, prompt: str, reference_image_bytes: bytes = None) -> bytes:
    contents = [prompt]
    if reference_image_bytes:
        contents.append(
            types.Part.from_bytes(data=reference_image_bytes, mime_type="image/png")
        )

    resp = client.models.generate_content(
        model=settings.image_bootstrap_model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    for candidate in resp.candidates:
        for part in candidate.content.parts:
            if part.inline_data:
                return part.inline_data.data

    raise RuntimeError("No image data returned from image generation model.")


def upload_asset_to_gcs(local_path: Path, gcs_uri: str) -> None:
    print(f"Uploading {local_path} to {gcs_uri}...")
    cmd = ["gcloud", "storage", "cp", str(local_path), gcs_uri]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"GCS upload failed: {res.stderr}")
    print(f"✓ Uploaded {gcs_uri}")


def create_contact_sheet(plate_paths: Dict[str, Path], output_path: Path) -> Path:
    from PIL import Image, ImageDraw

    # All plates are 9:16 (e.g. 720x1280 or similar).
    # Resize thumbnails to 360x640 for the contact sheet.
    thumb_w, thumb_h = 360, 640
    padding = 20
    header_h = 50
    total_w = (thumb_w * len(plate_paths)) + (padding * (len(plate_paths) + 1))
    total_h = thumb_h + (padding * 2) + header_h

    sheet = Image.new("RGB", (total_w, total_h), color=(15, 23, 42))  # slate-900 background
    draw = ImageDraw.Draw(sheet)

    for idx, (label, path) in enumerate(plate_paths.items()):
        if path.exists():
            img = Image.open(path)
            thumb = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = padding + idx * (thumb_w + padding)
            y = padding + header_h
            sheet.paste(thumb, (x, y))
            draw.text((x + 10, padding + 15), label, fill=(248, 250, 252))

    sheet.save(output_path)
    print(f"✓ Created master contact sheet at {output_path}")
    return output_path


def run_bootstrap(confirm: bool = False, local_only: bool = False):
    config = load_anchors_config()
    set_def = config["set"]
    anchors = config["anchors"]

    print("=" * 65)
    print("WEAWARE LATE NIGHT - ASSET BOOTSTRAP")
    print("=" * 65)
    print(f"Target Bucket: gs://{settings.gcs_bucket}")
    print(f"Image Model:   {settings.image_bootstrap_model}")
    print("Assets to generate:")
    print(f"  1. Set: {set_def['id']} (main backdrop)")
    for a in anchors:
        print(f"  2. Anchor '{a['name']}': medium & wide plates")
    print(f"Estimated Cost: ~$0.15 (5 images)")
    print("=" * 65)

    if not confirm:
        print("\n[SAFETY LOCK ACTIVE]")
        print("This script generates new master assets and consumes Vertex AI budget.")
        print("To execute asset generation, run:")
        print("  python video/bootstrap_assets.py --confirm [--local-only]")
        sys.exit(0)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "sets").mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "anchors").mkdir(parents=True, exist_ok=True)

    client = genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.location,
    )

    generated_plates: Dict[str, Path] = {}

    # 1. Generate Set Plate
    print("\n--- 1. Generating Set Plate ---")
    set_prompt = (
        f"{set_def['description']}. Empty newsroom desk with no people, "
        f"clean modern studio, vertical 9:16 composition, photorealistic broadcast lighting."
    )
    print(f"Generating studio set plate...")
    set_bytes = generate_image_with_modalities(client, set_prompt)
    set_path = ASSETS_DIR / "sets" / f"{set_def['id']}.png"
    set_path.write_bytes(set_bytes)
    generated_plates["Studio Main (Set)"] = set_path
    print(f"✓ Saved {set_path}")

    if not local_only:
        gcs_set_uri = set_def["reference_image_gcs_uri"].format(bucket=settings.gcs_bucket)
        upload_asset_to_gcs(set_path, gcs_set_uri)

    # 2. Derive Anchor Plates from Set Plate
    for anchor in anchors:
        aid = anchor["id"]
        aname = anchor["name"]
        print(f"\n--- Generating Anchor Plates for {aname} ---")

        # Medium framing
        medium_prompt = (
            f"Using the exact studio backdrop provided in the reference image, generate a medium shot of {aname}: "
            f"{anchor['description']}. Looking straight at the camera with an expressive broadcast smirk, "
            f"vertical 9:16 framing, perfect studio television lighting."
        )
        print(f"Generating {aid} medium plate...")
        med_bytes = generate_image_with_modalities(client, medium_prompt, reference_image_bytes=set_bytes)
        med_path = ASSETS_DIR / "anchors" / f"{aid}_medium.png"
        med_path.write_bytes(med_bytes)
        generated_plates[f"{aname} (Medium)"] = med_path
        print(f"✓ Saved {med_path}")

        # Wide framing
        wide_prompt = (
            f"Using the exact studio backdrop provided in the reference image, generate a wide desk shot of {aname}: "
            f"{anchor['description']}. Sitting behind the curved walnut desk, gesturing slightly with a pen, "
            f"vertical 9:16 framing, broadcast television composition."
        )
        print(f"Generating {aid} wide plate...")
        wide_bytes = generate_image_with_modalities(client, wide_prompt, reference_image_bytes=set_bytes)
        wide_path = ASSETS_DIR / "anchors" / f"{aid}_wide.png"
        wide_path.write_bytes(wide_bytes)
        generated_plates[f"{aname} (Wide)"] = wide_path
        print(f"✓ Saved {wide_path}")

        if not local_only:
            gcs_med = anchor["framings"]["medium"].format(bucket=settings.gcs_bucket)
            gcs_wide = anchor["framings"]["wide"].format(bucket=settings.gcs_bucket)
            upload_asset_to_gcs(med_path, gcs_med)
            upload_asset_to_gcs(wide_path, gcs_wide)

    # 3. Create Master Contact Sheet
    contact_sheet_path = ASSETS_DIR / "contact_sheet.png"
    create_contact_sheet(generated_plates, contact_sheet_path)
    if not local_only:
        upload_asset_to_gcs(contact_sheet_path, f"gs://{settings.gcs_bucket}/assets/contact_sheet.png")

    print("\n✓ Bootstrap complete! All anchor, set, and contact sheet plates generated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap set and anchor image plates")
    parser.add_argument("--confirm", action="store_true", help="Execute image generation (consumes budget)")
    parser.add_argument("--local-only", action="store_true", help="Save locally without uploading to GCS")
    args = parser.parse_args()
    run_bootstrap(confirm=args.confirm, local_only=args.local_only)
