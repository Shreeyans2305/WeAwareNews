# WeAware neutral news video

The video service turns a corroborated news story into a short, vertical WeAware News episode. It is designed for calm, attributed broadcast reporting. Satire, jokes, loaded language, unsupported claims, and editorial opinion are prohibited by the script and editor gates.

## Workflow

1. The picker selects a candidate with source coverage and ranks it for balanced, neutral reporting.
2. The scripter creates a short, structured script with attributed claims and clip-level dialogue.
3. The editor checks claims against source text and rejects factual distortion, missing attribution, loaded phrasing, unsupported causal links, or opinionated framing.
4. The pipeline generates presenter footage with Vertex AI Veo, then processes it with FFmpeg. Captions use a 1080 × 1920 layout; speech tails are trimmed and the final audio is normalized.
5. The assembled episode is stored and enters human review. A reviewer must approve it before the approved-video endpoint exposes it to the publishing integration. Approval does not itself publish the video.

Presenters and visuals are AI-generated. Captions and social metadata include an AI disclosure. Reviewers should still check the final video and source links; automated checks cannot guarantee factual accuracy or neutrality.

## Components

| Path | Responsibility |
| --- | --- |
| `pipeline/picker.py` | Ranks candidate stories |
| `pipeline/scripter.py` | Produces structured, attributed dialogue |
| `pipeline/editor.py` | Applies factual grounding and neutrality review |
| `pipeline/veo_client.py` | Selects model configuration and requests video generation |
| `pipeline/processor.py` | Generates captions, trims speech tails, joins clips, and normalizes audio |
| `pipeline/runner.py` | Orchestrates an episode run |
| `api/main.py` and `api/security.py` | Authenticated run and human review API |
| `config/settings.py` and `config/model_selector.py` | Runtime limits and model selection |
| `terraform/` | Cloud Run, workflow, storage, and related infrastructure |

## Human review security

Review links use time-limited, single-use HMAC tokens. Opening a review URL with `GET` displays the review page without changing episode state. The explicit `POST` commit action records approval or rejection and consumes the token. This prevents link scanners from approving a video simply by opening it. Keep the signing secret and API credentials in Secret Manager; never put them in frontend code or logs.

## Local development and checks

Use Python 3.12 and install `video/requirements.txt` in an isolated environment. Pipeline tests are in `video/tests/` and can be run with `pytest video/tests/`. Model selection and editor regression checks are available through `pipeline/check_models.py`; calls to hosted model services may incur cost and require credentials. The smoke-test script reports cost and needs an explicit spend decision before generation. Do not run Veo or image generation as part of routine local checks.

The pipeline settings define model tiers, generation duration, and spend limits. Review `config/settings.py`, `config/model_selector.py`, and the current Vertex AI pricing before changing model or resolution assumptions. Pricing and model availability change over time; estimates in issue notes or historical run logs are not current quotes.

## Deployment notes

The video API and runner are separate Cloud Run services. The workflow and Terraform sources live in `terraform/`. Deploying code does not approve or publish an episode. Keep Cloud Scheduler disabled unless an operator explicitly enables the intended schedule, and keep publishing in its separately controlled integration. Use the infrastructure plan and the project’s current operational credentials; never copy secret values into this README.

For system-wide context, see the [repository README](../README.md) and [architecture decisions](../DECISIONS.md).
