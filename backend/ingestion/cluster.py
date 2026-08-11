"""
Story clustering for the WeAware ingestion pipeline.

=== Two-stage hybrid clustering (CLUSTERING_MODE = "hybrid") ===

The fundamental problem with pure Jaccard-on-title: two outlets can cover
the same event with near-zero word overlap ("Police clash with protesters"
vs "Officers respond to violent riot"). This is especially acute when
sources span multiple languages.

The hybrid pipeline uses three layers in sequence:

  FAST-PATH (Jaccard short-circuit)
    If title word-overlap >= JACCARD_SHORT_CIRCUIT_THRESHOLD (default 0.5),
    assign immediately — same as the legacy path. No NLP models touched.
    Handles same-language near-identical headlines with zero added cost.

  STAGE A — Named-entity blocking (spaCy xx_ent_wiki_sm)
    Extract PER/ORG/LOC entities from (title + first ~2 sentences of
    raw_text) for both candidate items. Two items are blocking-candidates
    iff they share at least one entity string AND fall inside the
    time window. This cheaply prunes the candidate set before the
    expensive embedding step: if they share no entities they almost
    certainly don't cover the same event.

  STAGE B — Semantic centroid matching (multilingual-e5-base)
    For surviving Stage-A candidate pairs only, compute cosine similarity
    between the new item's sentence embedding and the running centroid of
    each open story. Assign to the nearest story whose centroid similarity
    >= EMBEDDING_COSINE_THRESHOLD (default 0.78), else open a new story.
    The centroid is updated incrementally as a running mean so we don't
    re-embed all prior items on each new arrival.

Model choice: intfloat/multilingual-e5-base (via sentence-transformers)
  - ~560 MB, 768-dim, strong MTEB multilingual similarity benchmarks
  - Better than LaBSE for pairwise similarity; smaller than LaBSE (~1.8 GB)
  - Requires "query: " prefix on inputs (handled internally below)
  - For news clustering (not retrieval) this prefix choice is debatable but
    consistent with the authors' own similarity examples.

NER model: spaCy xx_ent_wiki_sm
  - ~15 MB, CPU-friendly, covers ~7 languages (EN/DE/FR/ES/PT/IT/NL)
  - Good enough for entity-based blocking; not expected to extract every
    entity in every language, just enough shared tokens to gate Stage B.
  - Multilingual coverage gaps mean Stage B may still catch cases Stage A
    misses for rarer languages — that's acceptable (false-negative blocking
    just means the embedding comparison is skipped, leading to a new story).

=== Legacy mode (CLUSTERING_MODE = "jaccard") ===

  Falls through to the original O(n·clusters) Jaccard loop with no models
  loaded, identical output to the prior implementation.

=== Configuration ===

  CLUSTERING_MODE              str   "hybrid" | "jaccard"   default: "hybrid"  (env: WEAWARE_CLUSTERING_MODE)
  TITLE_WINDOW_HOURS           int    6                      (env: WEAWARE_CLUSTER_WINDOW_HOURS)
  JACCARD_THRESHOLD            float  0.5   legacy threshold & hybrid short-circuit
  JACCARD_SHORT_CIRCUIT        float  0.5   items above this skip Stage A/B
  EMBEDDING_COSINE_THRESHOLD   float  0.85  Stage B assignment threshold
"""

from __future__ import annotations

import math
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ingestion.utils import UTC, normalize_text


# ---------------------------------------------------------------------------
# Module-level configuration constants (overridable via env vars)
# ---------------------------------------------------------------------------

CLUSTERING_MODE: str = os.getenv("WEAWARE_CLUSTERING_MODE", "hybrid").lower()
"""
"jaccard"  — pure title word-overlap (original behavior, no NLP models loaded)
"hybrid"   — Jaccard fast-path → Stage A entity blocking → Stage B embeddings
"""

TITLE_WINDOW_HOURS: int = int(os.getenv("WEAWARE_CLUSTER_WINDOW_HOURS", "6"))
"""Items further apart than this (hours) are never compared. Configurable."""

JACCARD_THRESHOLD: float = 0.5
"""Legacy Jaccard threshold. Also used as the short-circuit cutoff in hybrid mode."""

JACCARD_SHORT_CIRCUIT: float = 0.5
"""
In hybrid mode: if Jaccard >= this value, assign to cluster immediately
without running Stage A or B. Identical to the legacy threshold so
same-language near-identical headlines cluster with zero model cost.
"""

EMBEDDING_COSINE_THRESHOLD: float = 0.90
"""Stage B cosine similarity threshold for centroid-nearest assignment."""

_NER_MODEL_NAME: str = "xx_ent_wiki_sm"
_WIKINEURAL_MODEL_NAME: str = "Babelscape/wikineural-multilingual-ner"
_EMBED_MODEL_NAME: str = "intfloat/multilingual-e5-base"
_EMBED_PREFIX: str = "query: "   # required prefix for multilingual-e5 inputs
_NER_SENTENCE_LIMIT: int = 2     # how many sentences of raw_text to feed NER
_EMBED_SENTENCE_LIMIT: int = 2   # same for embedding
NER_MODEL: str = os.getenv("WEAWARE_NER_MODEL", "wikineural").lower()


# ---------------------------------------------------------------------------
# Lazy model singletons — never imported at module load time
# ---------------------------------------------------------------------------

_nlp: Any = None        # spaCy Language pipeline
_wiki_nlp: Any = None   # transformers pipeline for wikineural
_embedder: Any = None   # SentenceTransformer


def _get_nlp() -> Any:
    """Load spaCy multilingual model on first hybrid use."""
    global _nlp
    if _nlp is None:
        try:
            import spacy  # type: ignore[import]
            _nlp = spacy.load(_NER_MODEL_NAME)
        except OSError:
            raise RuntimeError(
                f"spaCy model '{_NER_MODEL_NAME}' not found. "
                f"Run: python -m spacy download {_NER_MODEL_NAME}"
            )
    return _nlp

def _get_wiki_nlp() -> Any:
    """Load transformers pipeline for wikineural NER."""
    global _wiki_nlp
    if _wiki_nlp is None:
        try:
            from transformers import pipeline # type: ignore[import]
            _wiki_nlp = pipeline("ner", model=_WIKINEURAL_MODEL_NAME, aggregation_strategy="simple")
        except ImportError:
            raise RuntimeError(
                "transformers not installed. "
                "Run: pip install transformers"
            )
    return _wiki_nlp


def _get_embedder() -> Any:
    """Load sentence-transformers model on first hybrid use."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        _embedder = SentenceTransformer(_EMBED_MODEL_NAME)
    return _embedder


# ---------------------------------------------------------------------------
# Shared helpers (used by both modes)
# ---------------------------------------------------------------------------

def _parse_dt(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def _word_overlap_ratio(a: str, b: str) -> float:
    """Jaccard similarity on word sets (0–1)."""
    words_a, words_b = set(a.split()), set(b.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _within_window(
    dt_a: Optional[datetime],
    dt_b: Optional[datetime],
    window_hours: int,
) -> bool:
    """Return True if both timestamps are within window_hours of each other, or either is None."""
    if dt_a is None or dt_b is None:
        return True   # no timestamp = conservative, allow comparison
    return abs((dt_a - dt_b).total_seconds()) <= window_hours * 3600


def _make_ner_input(title: str, raw_text: str, sentence_limit: int) -> str:
    """title + first N sentences of raw_text, joined."""
    sentences = re.split(r"(?<=[.!?])\s+", raw_text.strip())
    body_snippet = " ".join(sentences[:sentence_limit])
    return f"{title}. {body_snippet}".strip()


def _make_embed_input(title: str, raw_text: str, sentence_limit: int) -> str:
    """Prefix + title + first N sentences of raw_text for e5."""
    sentences = re.split(r"(?<=[.!?])\s+", raw_text.strip())
    body_snippet = " ".join(sentences[:sentence_limit])
    text = f"{title}. {body_snippet}".strip()
    return f"{_EMBED_PREFIX}{text}"


# ---------------------------------------------------------------------------
# Stage A — Named-entity extraction and blocking
# ---------------------------------------------------------------------------

def _extract_entities(text: str) -> frozenset[str]:
    """
    Return a frozenset of lowercased entity surface forms (PER/ORG/LOC/MISC)
    extracted from `text` using either spaCy or wikineural depending on config.
    Returns an empty frozenset if unavailable or text is empty.
    """
    if not text.strip():
        return frozenset()
    
    if NER_MODEL == "wikineural":
        nlp = _get_wiki_nlp()
        ents = nlp(text)
        return frozenset(ent["word"].lower().strip() for ent in ents if ent["word"].strip())
    else:
        nlp = _get_nlp()
        doc = nlp(text)
        return frozenset(ent.text.lower().strip() for ent in doc.ents if ent.text.strip())


def _entities_share_any(set_a: frozenset[str], set_b: frozenset[str]) -> bool:
    return bool(set_a & set_b)


# ---------------------------------------------------------------------------
# Stage B — Embedding and centroid operations
# ---------------------------------------------------------------------------

def _embed(text: str) -> np.ndarray:
    """Embed one string to a unit-normalised numpy vector."""
    embedder = _get_embedder()
    # encode() returns a 2-D array for a list; [0] gives the 1-D vector.
    # normalize_embeddings=True gives unit vectors, making dot == cosine.
    vec: np.ndarray = embedder.encode(
        [text], normalize_embeddings=True, show_progress_bar=False
    )[0]
    return vec


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for pre-normalised vectors (dot product)."""
    return float(np.dot(a, b))


def _update_centroid(centroid: np.ndarray, new_vec: np.ndarray, n: int) -> np.ndarray:
    """
    Incremental running mean: new_centroid = (centroid * n + new_vec) / (n + 1).
    The result is NOT re-normalised — it's a true mean, not a unit vector.
    Cosine similarity against a non-unit centroid still works correctly
    (just slightly different from comparing two unit embeddings).
    """
    return (centroid * n + new_vec) / (n + 1)


def _centroid_to_json(centroid: np.ndarray) -> str:
    return json.dumps(centroid.tolist())


def _centroid_from_json(s: Optional[str]) -> Optional[np.ndarray]:
    if not s:
        return None
    return np.array(json.loads(s), dtype=np.float32)


# ---------------------------------------------------------------------------
# Internal cluster-head state (used only in hybrid mode)
# ---------------------------------------------------------------------------
#
# cluster_heads_hybrid: list of dicts, one per open story:
#   {
#     "story_id":   str,
#     "norm_title":  str,
#     "pub_dt":      Optional[datetime],
#     "hashes":      List[str],
#     "entities":    frozenset[str],
#     "centroid":    Optional[np.ndarray],
#     "member_count": int,    # for running-mean denominator
#   }


def _assign_hybrid(
    item: Dict,
    cluster_heads: List[Dict],
    window_hours: int,
    df: Dict[str, int],
    N: int,
) -> Optional[int]:
    """
    Try to assign `item` to an existing cluster using the hybrid pipeline.

    Returns the index into cluster_heads of the matched story, or None if
    no suitable story was found (caller should open a new story).
    """
    title = normalize_text(str(item.get("title") or ""))
    raw_text = normalize_text(str(item.get("raw_text") or ""))
    norm_title = _normalise_title(title)
    pub_dt = _parse_dt(str(item.get("published_at") or "") or None)

    # ---- Jaccard fast-path ------------------------------------------------
    # Check all open stories regardless of entity match; if any title is
    # very similar we short-circuit and avoid NLP model invocations entirely.
    for idx, head in enumerate(cluster_heads):
        if not _within_window(pub_dt, head["pub_dt"], window_hours):
            continue
        if _word_overlap_ratio(norm_title, head["norm_title"]) >= JACCARD_SHORT_CIRCUIT:
            return idx

    STRICT_EMBEDDING_THRESHOLD = 0.92
    MIN_ENTITY_MATCH_SCORE = 4.5

    # ---- Stage A — entity blocking ----------------------------------------
    item_entities = item.get("_entities", frozenset())

    # Collect candidate cluster indices and their required threshold
    # Tuple of (cluster_idx, required_threshold)
    candidates: List[Tuple[int, float]] = []
    
    # Asymmetric case counter
    asymmetric_zero_entity_count = 0

    for idx, head in enumerate(cluster_heads):
        if not _within_window(pub_dt, head["pub_dt"], window_hours):
            continue
            
        head_entities = head["entities"]
        
        if not item_entities and not head_entities:
            # FIX A: Both have zero entities -> proceed with strict threshold
            candidates.append((idx, STRICT_EMBEDDING_THRESHOLD))
        elif (not item_entities and head_entities) or (item_entities and not head_entities):
            # FIX A: Asymmetric case (only one has zero entities)
            # Use the strict threshold because a mismatch in entities implies risk.
            asymmetric_zero_entity_count += 1
            candidates.append((idx, STRICT_EMBEDDING_THRESHOLD))
        else:
            shared = item_entities & head_entities
            if shared:
                # Calculate match_score using IDF: weight(e) = log(N / df(e))
                # df(e) is guaranteed to be >= 1 since it appears in shared entities.
                MIN_SINGLE_ENTITY_WEIGHT = 4.0
                match_score = sum(math.log(N / df[e]) for e in shared if e in df)
                max_single = max((math.log(N / df[e]) for e in shared if e in df), default=0.0)
                if match_score >= MIN_ENTITY_MATCH_SCORE and max_single >= MIN_SINGLE_ENTITY_WEIGHT:
                    candidates.append((idx, EMBEDDING_COSINE_THRESHOLD))

    if not candidates:
        return None  # no candidates → new story

    # ---- Stage B — nearest-centroid cosine --------------------------------
    embed_input = _make_embed_input(title, raw_text, _EMBED_SENTENCE_LIMIT)
    item_vec = _embed(embed_input)

    best_idx: Optional[int] = None
    best_sim: float = -1.0

    for idx, required_threshold in candidates:
        centroid = cluster_heads[idx].get("centroid")
        if centroid is None:
            continue  # story has no embedding yet
        sim = _cosine(item_vec, centroid)
        if sim >= required_threshold and sim > best_sim:
            best_sim = sim
            best_idx = idx

    # Store embedding on item so caller can update centroid
    item["_embed_vec"] = item_vec
    return best_idx


# ---------------------------------------------------------------------------
# Public API — cluster_items()
# ---------------------------------------------------------------------------

def cluster_items(
    items: List[Dict],
    similarity_threshold: float = JACCARD_THRESHOLD,
    window_hours: int = TITLE_WINDOW_HOURS,
    mode: str = CLUSTERING_MODE,
) -> Tuple[List[Dict], Dict[str, str]]:
    """
    Group news items into story clusters.

    Parameters
    ----------
    items               Normalised item dicts (must have item_hash, title,
                        raw_text, published_at, source_id).
    similarity_threshold Jaccard threshold (used in "jaccard" mode and as the
                        fast-path short-circuit in "hybrid" mode).
    window_hours        Items outside this time window are never compared.
    mode                "jaccard" | "hybrid". Falls back to "jaccard" on
                        any unrecognised value.

    Returns
    -------
    stories             List of story dicts:
                          story_id, source_count, recency,
                          item_hashes, centroid (JSON str, hybrid only)
    item_to_story       Dict mapping item_hash → story_id
    """
    if mode == "hybrid":
        return _cluster_hybrid(items, window_hours)
    return _cluster_jaccard(items, similarity_threshold, window_hours)


# ---------------------------------------------------------------------------
# Legacy Jaccard path (unchanged behaviour)
# ---------------------------------------------------------------------------

def _cluster_jaccard(
    items: List[Dict],
    similarity_threshold: float,
    window_hours: int,
) -> Tuple[List[Dict], Dict[str, str]]:
    # Each entry: (norm_title, pub_dt, story_id, hashes)
    cluster_heads: List[Tuple[str, Optional[datetime], str, List[str]]] = []
    item_to_story: Dict[str, str] = {}

    for item in items:
        norm_title = _normalise_title(normalize_text(str(item.get("title") or "")))
        pub_dt = _parse_dt(str(item.get("published_at") or "") or None)
        item_hash = str(item["item_hash"])

        placed = False
        for _norm, head_dt, story_id, hashes in cluster_heads:
            if pub_dt and head_dt:
                if abs((pub_dt - head_dt).total_seconds()) > window_hours * 3600:
                    continue
            if _word_overlap_ratio(norm_title, _norm) >= similarity_threshold:
                hashes.append(item_hash)
                item_to_story[item_hash] = story_id
                placed = True
                break

        if not placed:
            new_story_id = str(uuid.uuid4())
            cluster_heads.append((norm_title, pub_dt, new_story_id, [item_hash]))
            item_to_story[item_hash] = new_story_id

    return _build_story_records_jaccard(items, cluster_heads, item_to_story)


def _build_story_records_jaccard(
    items: List[Dict],
    cluster_heads: List[Tuple[str, Optional[datetime], str, List[str]]],
    item_to_story: Dict[str, str],
) -> Tuple[List[Dict], Dict[str, str]]:
    hash_to_item: Dict[str, Dict] = {str(i["item_hash"]): i for i in items}
    stories: List[Dict] = []

    for _norm_title, _head_dt, story_id, hashes in cluster_heads:
        recency_candidates = [
            str(hash_to_item[h]["published_at"])
            for h in hashes
            if hash_to_item.get(h, {}).get("published_at")
        ]
        recency = max(recency_candidates) if recency_candidates else datetime.now(UTC).isoformat()
        stories.append(
            {
                "story_id": story_id,
                "source_count": len({
                    hash_to_item[h].get("source_id") for h in hashes if h in hash_to_item
                }),
                "recency": recency,
                "item_hashes": hashes,
                "centroid": None,   # no centroid in jaccard mode
            }
        )

    return stories, item_to_story


# ---------------------------------------------------------------------------
# Hybrid path
# ---------------------------------------------------------------------------

def _cluster_hybrid(
    items: List[Dict],
    window_hours: int,
) -> Tuple[List[Dict], Dict[str, str]]:
    cluster_heads: List[Dict] = []
    item_to_story: Dict[str, str] = {}
    
    N = len(items)
    df: Dict[str, int] = defaultdict(int)
    
    # Pre-pass: extract entities to compute global document frequencies (DF) for this batch
    for item in items:
        title = normalize_text(str(item.get("title") or ""))
        raw_text = normalize_text(str(item.get("raw_text") or ""))
        ner_input = _make_ner_input(title, raw_text, _NER_SENTENCE_LIMIT)
        ents = _extract_entities(ner_input)
        item["_entities"] = ents
        for e in ents:
            df[e] += 1

    for item in items:
        title = normalize_text(str(item.get("title") or ""))
        raw_text = normalize_text(str(item.get("raw_text") or ""))
        norm_title = _normalise_title(title)
        pub_dt = _parse_dt(str(item.get("published_at") or "") or None)
        item_hash = str(item["item_hash"])

        # _assign_hybrid also sets item["_embed_vec"] as a side-effect when
        # Stage B runs, so we can reuse it for the centroid update below.
        matched_idx = _assign_hybrid(item, cluster_heads, window_hours, df, N)

        if matched_idx is not None:
            head = cluster_heads[matched_idx]
            head["hashes"].append(item_hash)
            item_to_story[item_hash] = head["story_id"]

            # Update centroid if we have a fresh embedding from Stage B
            new_vec: Optional[np.ndarray] = item.pop("_embed_vec", None)
            if new_vec is not None and head["centroid"] is not None:
                n = head["member_count"]
                head["centroid"] = _update_centroid(head["centroid"], new_vec, n)
                head["member_count"] = n + 1
            # Also extend the entity set
            head["entities"] = head["entities"] | item.get("_entities", frozenset())
        else:
            # Open a new story — embed this item to seed the centroid
            embed_input = _make_embed_input(title, raw_text, _EMBED_SENTENCE_LIMIT)
            # Reuse cached vec if Stage B already computed it
            seed_vec: Optional[np.ndarray] = item.pop("_embed_vec", None)
            if seed_vec is None:
                seed_vec = _embed(embed_input)

            entities = item.get("_entities", frozenset())
            new_story_id = str(uuid.uuid4())
            cluster_heads.append(
                {
                    "story_id": new_story_id,
                    "norm_title": norm_title,
                    "pub_dt": pub_dt,
                    "hashes": [item_hash],
                    "entities": entities,
                    "centroid": seed_vec,
                    "member_count": 1,
                }
            )
            item_to_story[item_hash] = new_story_id

    return _build_story_records_hybrid(items, cluster_heads, item_to_story)


def _build_story_records_hybrid(
    items: List[Dict],
    cluster_heads: List[Dict],
    item_to_story: Dict[str, str],
) -> Tuple[List[Dict], Dict[str, str]]:
    hash_to_item: Dict[str, Dict] = {str(i["item_hash"]): i for i in items}
    stories: List[Dict] = []

    for head in cluster_heads:
        hashes = head["hashes"]
        recency_candidates = [
            str(hash_to_item[h]["published_at"])
            for h in hashes
            if hash_to_item.get(h, {}).get("published_at")
        ]
        recency = max(recency_candidates) if recency_candidates else datetime.now(UTC).isoformat()
        centroid = head.get("centroid")
        stories.append(
            {
                "story_id": head["story_id"],
                "source_count": len({
                    hash_to_item[h].get("source_id") for h in hashes if h in hash_to_item
                }),
                "recency": recency,
                "item_hashes": hashes,
                "centroid": _centroid_to_json(centroid) if centroid is not None else None,
            }
        )

    return stories, item_to_story
