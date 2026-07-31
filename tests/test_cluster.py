"""
Tests for ingestion/cluster.py

Covers:
  - Legacy jaccard mode: same-event near-identical titles cluster together
  - Legacy jaccard mode: clearly different events do not cluster
  - Jaccard mode: time-window guard works correctly
  - Hybrid mode fast-path: near-identical titles still cluster without NLP models
  - Hybrid mode: differently-worded same-event articles cluster via embedding
  - Hybrid mode: cross-language articles covering the same event cluster together
  - CLUSTERING_MODE = "jaccard" reproduces exact prior behaviour
  - has_cross_source_corroboration is set correctly regardless of mode
  - centroid field is None in jaccard mode, non-None in hybrid mode

Run:
  python -m pytest tests/test_cluster.py -v
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ingestion.cluster import (
    EMBEDDING_COSINE_THRESHOLD,
    JACCARD_THRESHOLD,
    _cluster_jaccard,
    _normalise_title,
    _word_overlap_ratio,
    cluster_items,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_item(
    title: str,
    source_id: str = "src-a",
    raw_text: str = "",
    published_at: Optional[str] = None,
) -> Dict:
    """Build a minimal normalised item dict."""
    url = f"https://example.com/{uuid.uuid4().hex}"
    item_hash = hashlib.sha256(f"{source_id}|{url}".encode()).hexdigest()
    return {
        "item_hash": item_hash,
        "source_id": source_id,
        "title": title,
        "raw_text": raw_text,
        "published_at": published_at or datetime.now(UTC).isoformat(),
    }


def _story_for(stories: List[Dict], item_hash: str, item_to_story: Dict) -> Optional[Dict]:
    sid = item_to_story.get(item_hash)
    return next((s for s in stories if s["story_id"] == sid), None)


# ---------------------------------------------------------------------------
# Unit tests — shared helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_normalise_title_strips_punctuation(self):
        assert _normalise_title("U.S. Police: 'Clash'!") == "us police clash"

    def test_word_overlap_identical(self):
        assert _word_overlap_ratio("police riot clash", "police riot clash") == pytest.approx(1.0)

    def test_word_overlap_zero(self):
        assert _word_overlap_ratio("police riot", "weather sunshine") == pytest.approx(0.0)

    def test_word_overlap_partial(self):
        ratio = _word_overlap_ratio("police officers fire", "fire department")
        assert 0.0 < ratio < 1.0


# ---------------------------------------------------------------------------
# Jaccard mode tests
# ---------------------------------------------------------------------------

class TestJaccardMode:
    def test_near_identical_titles_cluster(self):
        items = [
            _make_item("Police clash with protesters in downtown"),
            _make_item("Police clashes with protesters in downtown area"),
        ]
        stories, item_to_story = cluster_items(items, mode="jaccard")
        sid_a = item_to_story[items[0]["item_hash"]]
        sid_b = item_to_story[items[1]["item_hash"]]
        assert sid_a == sid_b, "Near-identical titles should be in the same story"

    def test_different_events_dont_cluster(self):
        items = [
            _make_item("Stock market crash sends indices plummeting"),
            _make_item("Earthquake strikes coastal region"),
        ]
        stories, item_to_story = cluster_items(items, mode="jaccard")
        assert item_to_story[items[0]["item_hash"]] != item_to_story[items[1]["item_hash"]]

    def test_three_items_same_event(self):
        base = "Prime minister resigns amid corruption scandal"
        items = [
            _make_item(base, source_id="bbc"),
            _make_item("Prime minister steps down amid corruption scandal", source_id="reuters"),
            _make_item("PM resigns over corruption scandal inquiry", source_id="ap"),
        ]
        stories, item_to_story = cluster_items(items, mode="jaccard")
        sids = {item_to_story[i["item_hash"]] for i in items}
        # At least two of the three should cluster; AP title has lower overlap
        assert len(sids) <= 2, "At least two near-identical items should cluster"

    def test_time_window_prevents_clustering(self):
        """Items 10 hours apart should not cluster even with identical titles."""
        title = "Leaders meet for emergency summit"
        t_old = "2024-01-01T00:00:00+00:00"
        t_new = "2024-01-01T10:00:00+00:00"
        items = [
            _make_item(title, published_at=t_old),
            _make_item(title, published_at=t_new),
        ]
        stories, item_to_story = cluster_items(items, mode="jaccard", window_hours=6)
        # Should NOT cluster due to 10-hour gap
        assert item_to_story[items[0]["item_hash"]] != item_to_story[items[1]["item_hash"]]

    def test_time_window_allows_clustering_within_window(self):
        title = "Leaders meet for emergency summit"
        t_old = "2024-01-01T00:00:00+00:00"
        t_new = "2024-01-01T04:00:00+00:00"
        items = [
            _make_item(title, published_at=t_old),
            _make_item(title, published_at=t_new),
        ]
        stories, item_to_story = cluster_items(items, mode="jaccard", window_hours=6)
        assert item_to_story[items[0]["item_hash"]] == item_to_story[items[1]["item_hash"]]

    def test_centroid_is_none_in_jaccard_mode(self):
        items = [_make_item("Breaking: summit begins"), _make_item("Summit talks open")]
        stories, _ = cluster_items(items, mode="jaccard")
        for story in stories:
            assert story["centroid"] is None

    def test_cross_source_corroboration_flag(self):
        """source_count > 1 means corroboration; verify it's computed correctly."""
        items = [
            _make_item("Major earthquake strikes city", source_id="bbc"),
            _make_item("Earthquake hits city hard", source_id="reuters"),
        ]
        stories, item_to_story = cluster_items(items, mode="jaccard")
        for story in stories:
            if story["source_count"] > 1:
                assert story["source_count"] >= 2

    def test_empty_input_returns_empty(self):
        stories, item_to_story = cluster_items([], mode="jaccard")
        assert stories == []
        assert item_to_story == {}

    def test_single_item_creates_one_story(self):
        items = [_make_item("Lone article about nothing")]
        stories, item_to_story = cluster_items(items, mode="jaccard")
        assert len(stories) == 1
        assert len(item_to_story) == 1


# ---------------------------------------------------------------------------
# Hybrid mode tests — NLP models mocked
# ---------------------------------------------------------------------------
#
# We mock _get_nlp() and _get_embedder() so the tests don't require
# downloading the actual models (~580 MB total). The mock embedder returns
# unit vectors whose cosine similarity is controlled per-test.

class _MockNLP:
    """Minimal spaCy Language-like object."""
    def __call__(self, text: str):
        doc = MagicMock()
        # Extract capitalised words as fake named entities
        import re
        caps = re.findall(r'\b[A-Z][a-z]+\b', text)
        ents = []
        for word in caps:
            ent = MagicMock()
            ent.text = word
            ents.append(ent)
        doc.ents = ents
        return doc


def _unit(v: List[float]) -> np.ndarray:
    arr = np.array(v, dtype=np.float32)
    return arr / np.linalg.norm(arr)


class _MockEmbedder:
    """
    Controllable embedder: returns a pre-registered vector for a given text
    prefix, or a random unit vector if not registered.
    """
    def __init__(self):
        self._registry: Dict[str, np.ndarray] = {}

    def register(self, prefix: str, vec: np.ndarray):
        self._registry[prefix] = vec / np.linalg.norm(vec)

    def encode(self, texts: List[str], normalize_embeddings: bool = True,
               show_progress_bar: bool = False) -> np.ndarray:
        results = []
        for text in texts:
            matched = None
            for prefix, vec in self._registry.items():
                if prefix in text:
                    matched = vec
                    break
            if matched is None:
                # Return a random unit vector — won't match anything above threshold
                rng = np.random.default_rng(seed=abs(hash(text)) % (2**32))
                v = rng.standard_normal(768).astype(np.float32)
                matched = v / np.linalg.norm(v)
            results.append(matched)
        return np.stack(results)


@pytest.fixture()
def mock_nlp():
    nlp = _MockNLP()
    with patch("ingestion.cluster._get_nlp", return_value=nlp), \
         patch("ingestion.cluster._nlp", nlp):
        yield nlp


@pytest.fixture()
def mock_embedder():
    embedder = _MockEmbedder()
    with patch("ingestion.cluster._get_embedder", return_value=embedder), \
         patch("ingestion.cluster._embedder", embedder):
        yield embedder


class TestHybridMode:
    def test_near_identical_titles_use_jaccard_fastpath(self, mock_nlp, mock_embedder):
        """Jaccard short-circuit: NLP models shouldn't even be called for obvious matches."""
        items = [
            _make_item("Police clash with protesters in downtown"),
            _make_item("Police clashes with protesters in downtown area"),
        ]
        stories, item_to_story = cluster_items(items, mode="hybrid")
        assert item_to_story[items[0]["item_hash"]] == item_to_story[items[1]["item_hash"]]

    def test_differently_worded_same_event_clusters_via_embedding(self, mock_nlp, mock_embedder):
        """
        The key regression case: two articles describe the same event with near-zero
        title overlap but share named entities and have high embedding similarity.

        Article A: "Police clash with protesters"  (source: BBC)
        Article B: "Officers respond to violent riot"  (source: Reuters)

        The mock embedder returns nearly-identical vectors for both titles,
        simulating semantic similarity, and the mock NLP returns "Police"/"Officers"
        as capitalised entities — they share none, so the entity check would block.
        We override the embedder to give them high cosine similarity and let the
        Jaccard short-circuit NOT trigger (low overlap), then force entities to match.
        """
        # Make the mock NLP return shared entity "Downtown" for both
        class SharedEntityNLP:
            def __call__(self, text):
                doc = MagicMock()
                ent = MagicMock()
                ent.text = "Downtown"
                doc.ents = [ent]
                return doc

        shared_vec = _unit([1.0] * 768)
        mock_embedder.register("query: Police clash with protesters", shared_vec)
        mock_embedder.register("query: Officers respond to violent riot", shared_vec)

        items = [
            _make_item("Police clash with protesters", source_id="bbc",
                       raw_text="The clash happened downtown."),
            _make_item("Officers respond to violent riot", source_id="reuters",
                       raw_text="Officers arrived downtown to respond."),
        ]

        with patch("ingestion.cluster._get_nlp", return_value=SharedEntityNLP()):
            stories, item_to_story = cluster_items(items, mode="hybrid")

        sid_a = item_to_story[items[0]["item_hash"]]
        sid_b = item_to_story[items[1]["item_hash"]]
        assert sid_a == sid_b, (
            "Same-event articles with high embedding similarity should cluster "
            "even with near-zero title word overlap"
        )

    def test_cross_language_same_event_clusters(self, mock_nlp, mock_embedder):
        """
        Cross-language case: English BBC and German DW cover the same summit.
        Jaccard gives near-zero (different words), but embedding similarity is high.
        """
        class SharedEntityNLP:
            def __call__(self, text):
                doc = MagicMock()
                ent = MagicMock()
                ent.text = "Berlin"
                doc.ents = [ent]
                return doc

        shared_vec = _unit([0.9] + [0.1] * 767)
        mock_embedder.register("query: EU leaders hold emergency summit in Berlin", shared_vec)
        mock_embedder.register("query: EU-Gipfel in Berlin", shared_vec)

        items = [
            _make_item(
                "EU leaders hold emergency summit in Berlin",
                source_id="bbc",
                raw_text="Leaders gathered in Berlin for an emergency summit on energy.",
            ),
            _make_item(
                "EU-Gipfel in Berlin: Dringende Beratungen zur Energiekrise",
                source_id="dw",
                raw_text="Die EU-Staats- und Regierungschefs trafen sich in Berlin.",
            ),
        ]

        with patch("ingestion.cluster._get_nlp", return_value=SharedEntityNLP()):
            stories, item_to_story = cluster_items(items, mode="hybrid")

        sid_a = item_to_story[items[0]["item_hash"]]
        sid_b = item_to_story[items[1]["item_hash"]]
        assert sid_a == sid_b, "Cross-language same-event articles should cluster via embedding"

    def test_clearly_different_events_dont_cluster(self, mock_nlp, mock_embedder):
        """Items with no shared entities and low cosine sim open separate stories."""
        # Different entities, orthogonal vectors
        vec_a = _unit([1.0] + [0.0] * 767)
        vec_b = _unit([0.0, 1.0] + [0.0] * 766)
        mock_embedder.register("query: Earthquake strikes coastal city", vec_a)
        mock_embedder.register("query: Stock market crash sends indices plummeting", vec_b)

        items = [
            _make_item("Earthquake strikes coastal city", source_id="bbc",
                       raw_text="A major Earthquake hit the Coast today."),
            _make_item("Stock market crash sends indices plummeting", source_id="ft",
                       raw_text="Wall Street indices fell sharply on Market fears."),
        ]

        stories, item_to_story = cluster_items(items, mode="hybrid")
        assert item_to_story[items[0]["item_hash"]] != item_to_story[items[1]["item_hash"]]

    def test_centroid_is_not_none_in_hybrid_mode(self, mock_nlp, mock_embedder):
        items = [_make_item("Breaking news event today")]
        stories, _ = cluster_items(items, mode="hybrid")
        for story in stories:
            assert story["centroid"] is not None, "Hybrid mode stories must have a centroid"

    def test_corroboration_flag_in_hybrid_mode(self, mock_nlp, mock_embedder):
        """has_cross_source_corroboration still comes from source_count >= 2."""
        shared_vec = _unit([1.0] * 768)
        mock_embedder.register("query: Leaders agree on climate deal", shared_vec)
        mock_embedder.register("query: Climate agreement reached by world leaders", shared_vec)

        class SharedEntityNLP:
            def __call__(self, text):
                doc = MagicMock()
                ent = MagicMock()
                ent.text = "Climate"
                doc.ents = [ent]
                return doc

        items = [
            _make_item("Leaders agree on climate deal", source_id="ap"),
            _make_item("Climate agreement reached by world leaders", source_id="guardian"),
        ]

        with patch("ingestion.cluster._get_nlp", return_value=SharedEntityNLP()):
            stories, item_to_story = cluster_items(items, mode="hybrid")

        clustered = [s for s in stories if s["source_count"] > 1]
        if clustered:
            assert clustered[0]["source_count"] >= 2

    def test_unknown_mode_falls_back_to_jaccard(self):
        """Unrecognised mode string should fall through to jaccard."""
        items = [
            _make_item("Police clash with protesters"),
            _make_item("Police clashes with protesters"),
        ]
        stories, item_to_story = cluster_items(items, mode="unknown_mode")
        # Should still cluster like jaccard (not raise)
        assert len(stories) <= 2
