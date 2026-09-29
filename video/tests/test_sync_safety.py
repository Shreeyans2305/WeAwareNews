"""
Test to verify that sync_to_postgres.py never overwrites posted=true
and never touches or alters video_runs columns or tables.
"""

import ast
import inspect
from pathlib import Path


def test_sync_to_postgres_never_overwrites_posted():
    """
    Inspect the SQL queries in sync_to_postgres.py to ensure that:
    1. The stories ON CONFLICT DO UPDATE clause does not update 'posted'.
    2. 'posted' is never overwritten or reset to false.
    """
    sync_file = Path("backend/sync_to_postgres.py")
    assert sync_file.exists()
    content = sync_file.read_text()

    # Verify the SQL update statement in sync_to_postgres.py
    assert "ON CONFLICT(story_id) DO UPDATE SET" in content
    assert "source_count = EXCLUDED.source_count" in content
    assert "recency      = EXCLUDED.recency" in content

    # Crucial check: verify 'posted' is NOT updated in ON CONFLICT
    lines = content.splitlines()
    in_story_conflict = False
    conflict_lines = []

    for line in lines:
        if "ON CONFLICT(story_id) DO UPDATE SET" in line:
            in_story_conflict = True
            continue
        if in_story_conflict:
            if '"""' in line or "execute_batch" in line:
                in_story_conflict = False
            else:
                conflict_lines.append(line.strip())

    conflict_block = "\n".join(conflict_lines)
    assert "posted = EXCLUDED.posted" not in conflict_block
    assert "posted = FALSE" not in conflict_block
    assert "posted" not in [l.split("=")[0].strip() for l in conflict_lines if "=" in l]


def test_sync_to_postgres_never_touches_video_runs():
    """
    Verify that sync_to_postgres.py does not mention or write to video_runs.
    """
    sync_file = Path("backend/sync_to_postgres.py")
    content = sync_file.read_text()

    assert "video_runs" not in content
    assert "video_status" not in content
    assert "video_claimed_at" not in content
