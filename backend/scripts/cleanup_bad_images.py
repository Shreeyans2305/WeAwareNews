#!/usr/bin/env python3
"""
cleanup_bad_images.py — NULL out bad image_url values in the deployed Postgres database.

Connects via Cloud SQL Proxy (psycopg2) and:
  1. Finds all items where image_url matches blocklist patterns (avatars, logos, etc.)
  2. Sets image_url = NULL for those rows
  3. Attempts to re-fetch a good image from the article URL's og:image
  4. Prints a summary of changes

Usage:
    python scripts/cleanup_bad_images.py              # dry-run (shows what would change)
    python scripts/cleanup_bad_images.py --apply      # actually apply changes
    python scripts/cleanup_bad_images.py --backfill   # also re-fetch images for cleaned rows
"""
import argparse
import os
import sys
import time
import urllib.request

import psycopg2
from bs4 import BeautifulSoup

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ingestion.image_filter import is_valid_editorial_image

PROXY_HOST = os.getenv("DB_HOST", "127.0.0.1")
PROXY_PORT = int(os.getenv("DB_PORT", "5433"))
DB_NAME = os.getenv("DB_NAME", "weaware")
DB_USER = os.getenv("DB_USER", "weaware_user")
GCP_PROJECT = os.getenv("GCP_PROJECT", "weaware")
SECRET_NAME = "db-password"


def get_db_password() -> str:
    """Read db-password from env var or Secret Manager."""
    pw = os.getenv("DB_PASS")
    if pw:
        return pw
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8").strip()
    except Exception:
        pass

    try:
        import subprocess
        result = subprocess.run(
            ["gcloud", "secrets", "versions", "access", "latest", f"--secret={SECRET_NAME}", f"--project={GCP_PROJECT}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"ERROR: Could not fetch db-password: {e}")
        sys.exit(1)


def get_db_connection():
    """Connect to Postgres via proxy."""
    pw = get_db_password()
    return psycopg2.connect(
        host=PROXY_HOST,
        port=PROXY_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=pw,
        connect_timeout=15,
    )


def get_image_for_url(url, timeout=10):
    """Fetch og:image from a URL, filtered through the editorial image validator."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as res:
            html = res.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            meta_og = soup.find("meta", property="og:image")
            if meta_og and meta_og.get("content"):
                img = meta_og["content"]
                if is_valid_editorial_image(img):
                    return img
            meta_tw = soup.find("meta", attrs={"name": "twitter:image"})
            if meta_tw and meta_tw.get("content"):
                img = meta_tw["content"]
                if is_valid_editorial_image(img):
                    return img
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Clean up bad image URLs in Postgres")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry-run)")
    parser.add_argument("--backfill", action="store_true", help="Re-fetch images for cleaned rows and published articles")
    parser.add_argument("--articles-only", action="store_true", help="Limit --apply to published article images")
    args = parser.parse_args()

    print(f"Connecting to Postgres at {PROXY_HOST}:{PROXY_PORT}...")
    conn = get_db_connection()
    cur = conn.cursor()

    # Find all items with bad image URLs
    cur.execute("SELECT item_hash, image_url, url, source_name, source_type FROM items WHERE image_url IS NOT NULL AND image_url != ''")
    all_rows = cur.fetchall()

    bad_rows = []
    good_rows = []
    for row in all_rows:
        item_hash, image_url, article_url, source_name, source_type = row
        if not is_valid_editorial_image(image_url):
            bad_rows.append(row)
        else:
            good_rows.append(row)

    print(f"\n=== Image Analysis ===")
    print(f"Total items with images: {len(all_rows)}")
    print(f"Valid editorial images:  {len(good_rows)}")
    print(f"Bad images to clean:     {len(bad_rows)}")

    # Published articles store their selected image separately from the item
    # records. Inspect these too, so the dry run reports the exact scope.
    cur.execute(
        "SELECT article_id, image_url, sources FROM editorial_articles "
        "WHERE status = 'published' AND image_url IS NOT NULL AND image_url != ''"
    )
    article_rows = cur.fetchall()
    bad_articles = [row for row in article_rows if not is_valid_editorial_image(row[1])]
    print(f"Published articles with invalid images: {len(bad_articles)}")
    print()

    if bad_rows:
        print("=== Bad Images Found (sample up to 20) ===")
        for item_hash, image_url, article_url, source_name, source_type in bad_rows[:20]:
            print(f"  [{source_type:20s}] {source_name:20s} | {image_url[:70]}...")

    if not args.apply:
        print(f"\n[DRY RUN] Would NULL out {len(bad_rows)} bad image_url values.")
        if bad_articles:
            print("Published articles to replace/clear:")
            for article_id, image_url, _sources in bad_articles[:20]:
                print(f"  {article_id} | {image_url[:100]}")
        print("Run with --apply to actually apply changes.")
        print("Run with --apply --backfill to also re-fetch images.")
        cur.close()
        conn.close()
        return

    # Published articles store their selected image separately from the item
    # records. Rebuild invalid article images from the article's own cited
    # source pages so existing content is corrected as well as future posts.
    article_replaced = 0
    for article_id, old_image, sources in bad_articles:
        replacement = None
        if args.backfill:
            for source in (sources or []):
                source_url = source.get("url") if isinstance(source, dict) else None
                if source_url:
                    replacement = get_image_for_url(source_url)
                    if replacement:
                        break
                    time.sleep(0.5)
        cur.execute(
            "UPDATE editorial_articles SET image_url = %s, updated_at = NOW() WHERE article_id = %s",
            (replacement, article_id),
        )
        article_replaced += bool(replacement)
    conn.commit()
    print(f"Updated {len(bad_articles)} published article image(s); "
          f"replaced {article_replaced} image(s) where a safe source image was found.")

    if args.articles_only:
        cur.close()
        conn.close()
        print("Published article image cleanup complete.")
        return

    # Apply: NULL out bad image URLs
    nulled = 0
    for item_hash, image_url, article_url, source_name, source_type in bad_rows:
        cur.execute("UPDATE items SET image_url = NULL WHERE item_hash = %s", (item_hash,))
        nulled += 1
    conn.commit()
    print(f"\n✓ NULLed out {nulled} bad image_url values.")

    # Optionally re-fetch images
    if args.backfill:
        print(f"\nRe-fetching images for {len(bad_rows)} cleaned rows...")
        refetched = 0
        for item_hash, _, article_url, source_name, source_type in bad_rows:
            if not article_url:
                continue
            img = get_image_for_url(article_url)
            if img:
                cur.execute("UPDATE items SET image_url = %s WHERE item_hash = %s", (img, item_hash))
                conn.commit()
                print(f"  ✓ Found good image for [{source_name}] {article_url[:50]}...")
                refetched += 1
            time.sleep(0.5)
        print(f"\n✓ Re-fetched images for {refetched}/{len(bad_rows)} items.")

    cur.close()
    conn.close()
    print("\nCleanup complete.")


if __name__ == "__main__":
    main()
