"""
Integration tests for the ingestion pipeline.
These tests use real NLP models (spaCy, sentence-transformers) and do not mock out the clustering layer.
"""

import pytest
import os
from ingestion.cluster import _cluster_hybrid
from ingestion.utils import stable_item_hash, UTC
from datetime import datetime

@pytest.mark.slow
def test_hybrid_clustering_real_models():
    """
    Test that two items with near-zero title word overlap but a shared named entity
    correctly cluster into the same story using the real NLP pipeline.
    """
    now_iso = datetime.now(UTC).isoformat()
    
    # Fake article 1
    item1 = {
        "item_hash": stable_item_hash("fake1", "http://example.com/1"),
        "url": "http://example.com/1",
        "title": "President of Ukraine visits the frontlines in a surprise move",
        "raw_text": "Zelensky appeared near the eastern front today to boost morale among the troops.",
        "published_at": now_iso,
        "source_name": "Fake Source 1"
    }
    
    # Fake article 2 - zero title overlap with item1, but shares the entity "Zelensky" in text
    item2 = {
        "item_hash": stable_item_hash("fake2", "http://example.com/2"),
        "url": "http://example.com/2",
        "title": "Zelensky delivers speech to parliament regarding military supplies",
        "raw_text": "The Ukrainian leader gave an impassioned plea for more weapons during his address.",
        "published_at": now_iso,
        "source_name": "Fake Source 2"
    }

    # Actually, Jaccard uses title only. Item 1 title has "President of Ukraine...". Item 2 title has "Zelensky delivers...".
    # Wait, the hybrid clustering uses the concatenated title + raw_text for embedding matching.
    # We just pass the two items to _cluster_hybrid and verify they end up in the same story.
    
    items = [item1, item2]
    
    # Run the real hybrid clustering (this will load spaCy and e5 models)
    # 24 hours window
    stories, item_to_story = _cluster_hybrid(items, window_hours=24)
    
    # Assert they clustered together
    assert len(stories) == 1, "The two items should form exactly one story cluster."
    assert item_to_story[item1["item_hash"]] == item_to_story[item2["item_hash"]], "The items should have the same story ID."
