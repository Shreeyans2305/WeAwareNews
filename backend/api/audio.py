"""Background speech generation and audio delivery helpers for WeAware."""

import hashlib
import json
import logging
import os
import re
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _cloud_clients():
    try:
        from google.cloud import storage, tasks_v2, texttospeech
    except ImportError as exc:  # pragma: no cover - deployment configuration guard
        raise HTTPException(status_code=503, detail="Audio services are not installed") from exc
    return storage, tasks_v2, texttospeech


def content_hash(text: str, voice: str) -> str:
    return hashlib.sha256(f"{voice}\0{text}".encode("utf-8")).hexdigest()


def _voice_key(content_type: str) -> str:
    if content_type == "podcast":
        model = os.getenv("AUDIO_TTS_PODCAST_MODEL", "gemini-2.5-pro-tts")
        host_one = os.getenv("AUDIO_TTS_PODCAST_HOST_ONE", "Kore")
        host_two = os.getenv("AUDIO_TTS_PODCAST_HOST_TWO", "Charon")
        host_one_name = os.getenv("WEAWARE_PODCAST_HOST_ONE_NAME", "Rhea").strip() or "Rhea"
        host_two_name = os.getenv("WEAWARE_PODCAST_HOST_TWO_NAME", "Jay").strip() or "Jay"
        return f"podcast-dialogue-v2:{model}:{host_one_name}={host_one}:{host_two_name}={host_two}"
    return os.getenv("AUDIO_TTS_VOICE", "en-US-Neural2-D")


def _dialogue_turns(text: str) -> list[dict[str, str]]:
    """Extract labeled host turns; older approved monologue scripts return no turns."""
    host_one_name = os.getenv("WEAWARE_PODCAST_HOST_ONE_NAME", "Rhea").strip() or "Rhea"
    host_two_name = os.getenv("WEAWARE_PODCAST_HOST_TWO_NAME", "Jay").strip() or "Jay"
    if host_one_name.casefold() == host_two_name.casefold():
        raise ValueError("Podcast presenter names must be distinct")
    aliases = {
        host_one_name.casefold(): re.sub(r"[^A-Za-z0-9]", "", host_one_name),
        host_two_name.casefold(): re.sub(r"[^A-Za-z0-9]", "", host_two_name),
    }
    turns = []
    for line in text.splitlines():
        match = re.match(r"^\s*([^:]+)\s*:\s*(.*?)\s*$", line, flags=re.IGNORECASE)
        if not match or not match.group(2):
            continue
        label = match.group(1).strip().casefold()
        # Keep compatibility with scripts already in the editorial queue.
        legacy_aliases = {"host one": aliases[host_one_name.casefold()], "host two": aliases[host_two_name.casefold()]}
        speaker = aliases.get(label, legacy_aliases.get(label))
        if speaker:
            turns.append({"speaker": speaker, "text": match.group(2)})
    speakers = {turn["speaker"] for turn in turns}
    return turns if len(speakers) == 2 else []


def _dialogue_chunks(turns: list[dict[str, str]], max_bytes: int = 3000) -> list[list[dict[str, str]]]:
    """Group complete turns under Gemini TTS's 4,000-byte dialogue limit."""
    chunks: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    size = 0
    for turn in turns:
        words = turn["text"].split()
        parts = []
        part_words = []
        part_size = 0
        for word in words:
            word_size = len(word.encode("utf-8"))
            if word_size > max_bytes:
                raise ValueError("Podcast dialogue contains an unreasonably long token")
            needed = word_size + (1 if part_words else 0)
            if part_words and part_size + needed > max_bytes:
                parts.append(" ".join(part_words))
                part_words, part_size = [], 0
                needed = word_size
            part_words.append(word)
            part_size += needed
        if part_words:
            parts.append(" ".join(part_words))
        for part in parts:
            item = {"speaker": turn["speaker"], "text": part}
            # Leave margin for speaker labels and the style prompt.
            item_size = len(part.encode("utf-8")) + len(turn["speaker"]) + 12
            if current and size + item_size > max_bytes:
                chunks.append(current)
                current, size = [], 0
            current.append(item)
            size += item_size
    if current:
        chunks.append(current)
    return chunks


def queue_audio(content_type: str, content_id: str, digest: str) -> None:
    """Enqueue one idempotent generation request; the Cloud Tasks queue retries it."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("AUDIO_TASKS_LOCATION", "us-central1")
    queue = os.getenv("AUDIO_TASKS_QUEUE")
    worker_url = os.getenv("AUDIO_TASKS_WORKER_URL")
    service_account = os.getenv("AUDIO_TASKS_SERVICE_ACCOUNT")
    if not all((project, queue, worker_url, service_account)):
        raise HTTPException(status_code=503, detail="Audio generation is not configured")

    _, tasks_v2, _ = _cloud_clients()
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, location, queue)
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": worker_url.rstrip("/") + "/api/v1/audio/tasks",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"contentType": content_type, "contentId": content_id, "hash": digest}).encode(),
            "oidc_token": {"service_account_email": service_account, "audience": os.getenv("AUDIO_TASKS_AUDIENCE", worker_url)},
        },
        # Cloud Tasks uses this name for safe retries and duplicate requests.
        "name": client.task_path(project, location, queue, f"{content_type}-{content_id}-{digest[:24]}"),
    }
    try:
        client.create_task(request={"parent": parent, "task": task})
    except Exception as exc:
        # Already-exists means a previous request is already queued or completed.
        code = getattr(exc, "code", None)
        if callable(code):
            code = code()
        code_name = getattr(code, "name", "")
        if code != 6 and code_name != "ALREADY_EXISTS":
            logger.exception("Could not enqueue audio synthesis")
            raise HTTPException(status_code=503, detail="Could not queue audio generation") from exc


def _get_narration(db, content_type: str, content_id: str) -> tuple[str, str]:
    cur = db.cursor()
    try:
        if content_type == "article":
            cur.execute(
                "SELECT title, summary, body FROM editorial_articles WHERE article_id=%s AND status='published'",
                (content_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Article not found")
            body = row[2] or []
            if isinstance(body, str):
                body = json.loads(body)
            text = "\n\n".join(part for part in [row[0], row[1], *(body if isinstance(body, list) else [])] if part)
            return text, content_id
        if content_type == "podcast":
            cur.execute(
                "SELECT title, script FROM podcast_episodes WHERE episode_id=%s AND status IN ('approved','published')",
                (content_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Approved podcast episode not found")
            return f"{row[0]}\n\n{row[1]}", content_id
        raise HTTPException(status_code=400, detail="Unsupported audio content type")
    finally:
        cur.close()


def request_audio(db, content_type: str, content_id: str) -> dict:
    voice = _voice_key(content_type)
    text, _ = _get_narration(db, content_type, content_id)
    digest = content_hash(text, voice)
    cur = db.cursor()
    try:
        cur.execute("SELECT pg_advisory_xact_lock(78310421)")
        cur.execute("SELECT status,object_name,duration_seconds,error_message FROM audio_assets WHERE content_type=%s AND content_id=%s AND content_hash=%s AND voice_name=%s",
                    (content_type, content_id, digest, voice))
        existing = cur.fetchone()
        if not existing:
            # Reserve characters before creating a job so public article IDs cannot
            # be used to trigger unbounded synthesis spend. Reservations are
            # conservative and reset at the start of each calendar month.
            cur.execute("SELECT date_trunc('month',NOW())::date")
            month_start = cur.fetchone()[0]
            cur.execute("SELECT reserved_characters FROM audio_usage WHERE month_start=%s FOR UPDATE", (month_start,))
            usage_row = cur.fetchone()
            used = int(usage_row[0]) if usage_row else 0
            limit = int(os.getenv("AUDIO_TTS_MONTHLY_CHARACTER_LIMIT", "1000000"))
            if limit > 0 and used + len(text) > limit:
                db.rollback()
                raise HTTPException(status_code=429, detail="Monthly audio generation limit reached")
            cur.execute("""INSERT INTO audio_usage(month_start,reserved_characters) VALUES (%s,%s)
                           ON CONFLICT(month_start) DO UPDATE SET reserved_characters=audio_usage.reserved_characters+EXCLUDED.reserved_characters,updated_at=NOW()""",
                        (month_start, len(text)))
        else:
            cur.execute("SELECT date_trunc('month',NOW())::date")
            month_start = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO audio_assets(content_type, content_id, content_hash, voice_name, status,character_count,reserved_month)
               VALUES (%s,%s,%s,%s,'queued',%s,%s)
               ON CONFLICT(content_type, content_id, content_hash, voice_name)
               DO UPDATE SET status=CASE WHEN audio_assets.status='failed' THEN 'queued' ELSE audio_assets.status END,
                             error_message=CASE WHEN audio_assets.status='failed' THEN NULL ELSE audio_assets.error_message END,
                             updated_at=NOW()
               RETURNING status, object_name, duration_seconds, error_message""",
            (content_type, content_id, digest, voice, len(text), month_start),
        )
        status, object_name, duration, error = cur.fetchone()
        db.commit()
    finally:
        cur.close()

    if status == "queued":
        try:
            queue_audio(content_type, content_id, digest)
        except Exception:
            # Leave queued state intact: a later client request can enqueue again.
            raise
    return {"status": status, "audioUrl": _audio_url(content_type, object_name) if object_name else None,
            "durationSeconds": duration, "error": error, "contentHash": digest}


def audio_status(db, content_type: str, content_id: str) -> dict:
    voice = _voice_key(content_type)
    text, _ = _get_narration(db, content_type, content_id)
    digest = content_hash(text, voice)
    cur = db.cursor()
    try:
        cur.execute("SELECT status,object_name,duration_seconds,error_message FROM audio_assets WHERE content_type=%s AND content_id=%s AND content_hash=%s AND voice_name=%s",
                    (content_type, content_id, digest, voice))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return {"status": "not_requested", "audioUrl": None, "durationSeconds": None}
    return {"status": row[0], "audioUrl": _audio_url(content_type, row[1]) if row[1] else None,
            "durationSeconds": row[2], "error": row[3], "contentHash": digest}


def _audio_url(content_type: str, object_name: Optional[str]) -> Optional[str]:
    if not object_name:
        return None
    bucket_name = os.getenv("PODCAST_AUDIO_BUCKET" if content_type == "podcast" else "ARTICLE_AUDIO_BUCKET")
    if not bucket_name:
        return None
    storage, _, _ = _cloud_clients()
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    if content_type == "podcast":
        origin = os.getenv("PODCAST_AUDIO_PUBLIC_ORIGIN", f"https://storage.googleapis.com/{bucket_name}")
        return f"{origin.rstrip('/')}/{object_name}"
    try:
        # Cloud Run's metadata credentials have no private key. Use IAM
        # signBlob via google-auth's remote signer instead of local signing.
        import google.auth
        from google.auth.transport.requests import Request

        request = Request()
        credentials, _ = google.auth.default()
        if not credentials.valid:
            credentials.refresh(request)
        service_account_email = os.getenv("AUDIO_SIGNING_SERVICE_ACCOUNT") or getattr(
            credentials, "service_account_email", None
        )
        if not service_account_email:
            raise RuntimeError("Could not determine the audio signing service account")
        # IAM-managed signing keys can invalidate URLs longer than 12 hours.
        return blob.generate_signed_url(
            version="v4", expiration=12 * 60 * 60, method="GET",
            service_account_email=service_account_email, access_token=credentials.token,
        )
    except Exception:
        logger.exception("Could not sign article audio URL")
        return None


def _tts_chunks(text: str, max_bytes: int = 4500) -> list[str]:
    """Split on word boundaries below Cloud TTS's 5,000-byte request limit."""
    chunks = []
    current = []
    size = 0
    for word in text.split():
        encoded_size = len(word.encode("utf-8"))
        if encoded_size > max_bytes:
            raise ValueError("Narration contains an unreasonably long token")
        needed = encoded_size + (1 if current else 0)
        if current and size + needed > max_bytes:
            chunks.append(" ".join(current))
            current, size = [], 0
            needed = encoded_size
        current.append(word)
        size += needed
    if current:
        chunks.append(" ".join(current))
    return chunks


def _mp3_frames(audio: bytes) -> bytes:
    """Remove per-chunk ID3 headers/trailers before joining encoded MP3 frames."""
    if audio.startswith(b"ID3") and len(audio) >= 10:
        tag_size = sum((audio[6 + index] & 0x7F) << (7 * (3 - index)) for index in range(4))
        audio = audio[10 + tag_size + (10 if audio[5] & 0x10 else 0):]
    if len(audio) >= 128 and audio[-128:-125] == b"TAG":
        audio = audio[:-128]
    return audio


def _reserve_synthesis_attempt(db, content_type: str, content_id: str, digest: str, voice_name: str) -> None:
    cur = db.cursor()
    try:
        cur.execute("SELECT pg_advisory_xact_lock(78310421)")
        cur.execute("SELECT character_count,synthesis_attempts,reserved_month FROM audio_assets WHERE content_type=%s AND content_id=%s AND content_hash=%s AND voice_name=%s FOR UPDATE",
                    (content_type, content_id, digest, voice_name))
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Audio reservation disappeared")
        character_count, attempts = int(row[0]), int(row[1])
        cur.execute("SELECT date_trunc('month',NOW())::date")
        month_start = cur.fetchone()[0]
        reserved_month = row[2]
        if attempts > 0 or reserved_month != month_start:
            cur.execute("SELECT reserved_characters FROM audio_usage WHERE month_start=%s FOR UPDATE", (month_start,))
            usage_row = cur.fetchone()
            used = int(usage_row[0]) if usage_row else 0
            limit = int(os.getenv("AUDIO_TTS_MONTHLY_CHARACTER_LIMIT", "1000000"))
            if limit > 0 and used + character_count > limit:
                raise RuntimeError("Monthly audio generation limit reached; retry was not synthesized")
            cur.execute("""INSERT INTO audio_usage(month_start,reserved_characters) VALUES (%s,%s)
                           ON CONFLICT(month_start) DO UPDATE SET reserved_characters=audio_usage.reserved_characters+EXCLUDED.reserved_characters,updated_at=NOW()""",
                        (month_start, character_count))
        cur.execute("UPDATE audio_assets SET synthesis_attempts=synthesis_attempts+1,reserved_month=%s,updated_at=NOW() WHERE content_type=%s AND content_id=%s AND content_hash=%s AND voice_name=%s",
                    (month_start, content_type, content_id, digest, voice_name))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def process_audio_task(db, content_type: str, content_id: str, expected_hash: str) -> None:
    voice_name = _voice_key(content_type)
    text, _ = _get_narration(db, content_type, content_id)
    if content_hash(text, voice_name) != expected_hash:
        # A script/article changed while the task was waiting; the next request
        # will queue the current version instead of publishing stale audio.
        cur = db.cursor()
        try:
            cur.execute("UPDATE audio_assets SET status='failed',error_message='Narration changed before synthesis',updated_at=NOW() WHERE content_type=%s AND content_id=%s AND content_hash=%s AND voice_name=%s",
                        (content_type, content_id, expected_hash, voice_name))
            db.commit()
        finally:
            cur.close()
        return
    bucket_name = os.getenv("PODCAST_AUDIO_BUCKET" if content_type == "podcast" else "ARTICLE_AUDIO_BUCKET")
    if not bucket_name:
        raise RuntimeError("Audio storage bucket is not configured")

    storage, _, texttospeech = _cloud_clients()
    object_name = f"{content_type}/{content_id}/{expected_hash}.mp3"
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    # A retry after a successful synthesis but failed DB write reuses the object.
    if not blob.exists():
        _reserve_synthesis_attempt(db, content_type, content_id, expected_hash, voice_name)
        client = texttospeech.TextToSpeechClient()
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.0)
        audio_parts = []
        if content_type == "podcast":
            model = os.getenv("AUDIO_TTS_PODCAST_MODEL", "gemini-2.5-pro-tts")
            host_one = os.getenv("AUDIO_TTS_PODCAST_HOST_ONE", "Kore")
            host_two = os.getenv("AUDIO_TTS_PODCAST_HOST_TWO", "Charon")
            host_one_name = os.getenv("WEAWARE_PODCAST_HOST_ONE_NAME", "Rhea").strip() or "Rhea"
            host_two_name = os.getenv("WEAWARE_PODCAST_HOST_TWO_NAME", "Jay").strip() or "Jay"
            turns = _dialogue_turns(text)
            if turns:
                prompt = (
                    "Speak this as a warm, natural, clear news conversation between two experienced presenters. "
                    "Respond to each other naturally, use restrained human reactions, and preserve a calm, factual tone."
                )
                voice = texttospeech.VoiceSelectionParams(
                    language_code="en-US",
                    model_name=model,
                    multi_speaker_voice_config=texttospeech.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            texttospeech.MultispeakerPrebuiltVoice(
                                speaker_alias=re.sub(r"[^A-Za-z0-9]", "", host_one_name), speaker_id=host_one),
                            texttospeech.MultispeakerPrebuiltVoice(
                                speaker_alias=re.sub(r"[^A-Za-z0-9]", "", host_two_name), speaker_id=host_two),
                        ]
                    ),
                )
                for chunk in _dialogue_chunks(turns):
                    markup = texttospeech.MultiSpeakerMarkup(turns=chunk)
                    response = client.synthesize_speech(
                        input=texttospeech.SynthesisInput(multi_speaker_markup=markup, prompt=prompt),
                        voice=voice,
                        audio_config=audio_config,
                    )
                    audio_parts.append(_mp3_frames(response.audio_content))
            else:
                # Retain playback support for older, single-host episodes while new
                # drafts use the explicit two-host format above.
                voice = texttospeech.VoiceSelectionParams(
                    language_code="en-US", name=host_one, model_name=model
                )
                for chunk in _tts_chunks(text):
                    response = client.synthesize_speech(
                        input=texttospeech.SynthesisInput(
                            text=chunk,
                            prompt="Read this published news briefing clearly and naturally in a calm, conversational presenter voice.",
                        ),
                        voice=voice,
                        audio_config=audio_config,
                    )
                    audio_parts.append(_mp3_frames(response.audio_content))
        else:
            voice = texttospeech.VoiceSelectionParams(
                language_code="-".join(voice_name.split("-")[:2]), name=voice_name
            )
            for chunk in _tts_chunks(text):
                response = client.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=chunk),
                    voice=voice,
                    audio_config=audio_config,
                )
                audio_parts.append(_mp3_frames(response.audio_content))
        blob.upload_from_string(b"".join(audio_parts), content_type="audio/mpeg")
    blob.reload()
    estimated_duration = max(1, round(len(text.split()) / 2.5))
    cur = db.cursor()
    try:
        cur.execute(
            """UPDATE audio_assets SET status='ready', object_name=%s, size_bytes=%s,duration_seconds=%s,
               updated_at=NOW(), error_message=NULL
               WHERE content_type=%s AND content_id=%s AND content_hash=%s AND voice_name=%s""",
            (object_name, blob.size or 0, estimated_duration, content_type, content_id, expected_hash, voice_name),
        )
        db.commit()
    finally:
        cur.close()

