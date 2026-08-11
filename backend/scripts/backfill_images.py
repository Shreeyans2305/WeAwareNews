#!/usr/bin/env python3
"""
backfill_images.py — Fetch missing images for unposted corroborated stories.
Uses the Cloud SQL Python Connector (no proxy needed).
"""
import os
import urllib.request
from bs4 import BeautifulSoup
import time
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector, IPTypes
import pg8000

def get_image_for_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as res:
            html = res.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            meta_og = soup.find("meta", property="og:image")
            if meta_og and meta_og.get("content"):
                return meta_og["content"]
            meta_tw = soup.find("meta", attrs={"name": "twitter:image"})
            if meta_tw and meta_tw.get("content"):
                return meta_tw["content"]
    except Exception:
        pass
    return None

def main():
    print("Initializing...")
    client = secretmanager.SecretManagerServiceClient()
    project_id = "project-9ba21d45-1dfd-4108-b69"
    
    # Get DB password
    name = f"projects/{project_id}/secrets/db-password/versions/latest"
    pw = client.access_secret_version(request={"name": name}).payload.data.decode("UTF-8").strip()
    
    # Connect using Connector
    connector = Connector()
    conn = connector.connect(
        f"{project_id}:us-central1:weaware-pg",
        "pg8000",
        user="weaware_user",
        password=pw,
        db="weaware",
        ip_type=IPTypes.PUBLIC,
    )
    
    cur = conn.cursor()

    # Get all unposted corroborated stories
    cur.execute("SELECT story_id FROM stories WHERE source_count >= 2 AND posted = false")
    stories = cur.fetchall()

    updated = 0
    total = len(stories)
    print(f"Checking {total} stories for missing images...")

    for row in stories:
        story_id = row[0]
        # Check if story already has an image across its articles
        cur.execute("SELECT item_hash, url, image_url FROM items WHERE story_id = %s", (story_id,))
        items = cur.fetchall()
        
        has_image = any(item[2] for item in items)
        if has_image:
            continue
            
        # Try fetching image for items
        for item_hash, url, _ in items:
            img = get_image_for_url(url)
            if img:
                # pg8000 uses %s for placeholders but we need to pass them carefully
                cur.execute("UPDATE items SET image_url = %s WHERE item_hash = %s", (img, item_hash))
                conn.commit()
                print(f"Found image for story {story_id[:8]}... from {url[:30]}...")
                updated += 1
                break  # only need one image per story
        time.sleep(0.5)

    print(f"Backfilled images for {updated} stories.")
    cur.close()
    conn.close()
    connector.close()

if __name__ == "__main__":
    main()
