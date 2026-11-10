"""Score and summarise stories using Claude.

Calls run through the local `claude` CLI in headless mode (`claude -p`), which
uses the logged-in Claude subscription rather than pay-per-token API credits.
No ANTHROPIC_API_KEY is required.
"""

import json
import os
import subprocess
import traceback
from pathlib import Path
from typing import List
from digest.feeds import Story

# Model alias passed to `claude --model`; "sonnet" resolves to the latest Sonnet.
_MODEL = os.environ.get("CLAUDE_MODEL", "sonnet")
# CLI binary; override with CLAUDE_BIN if `claude` is not on PATH.
_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_CALL_TIMEOUT = 600  # seconds per batch

# Display names for the strands. These must match the strand names in rubric.md:
# if you rename a strand there, rename it here too.
STRANDS = {
    "ai-explained": "AI explained",
    "ai-honest": "AI, honestly",
    "health": "Health & evidence",
    "curiosity": "Curiosity",
}

# The rubric — the taste of the thing — lives in rubric.md at the project root, so it can be
# edited without touching code. Override the location with RUBRIC_PATH.
_RUBRIC_PATH = Path(
    os.environ.get("RUBRIC_PATH", Path(__file__).resolve().parent.parent / "rubric.md")
)


def load_rubric() -> str:
    """Read rubric.md and return it as the instruction sent to the model."""
    try:
        text = _RUBRIC_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(
            f"Rubric not found at {_RUBRIC_PATH}.\n"
            "Keep rubric.md next to run.py, or set RUBRIC_PATH to point at it."
        )
    if not text:
        raise SystemExit(f"Rubric at {_RUBRIC_PATH} is empty.")
    return text


_BATCH_SIZE = 30  # stories per API call to stay inside a safe prompt budget
_MAX_RETRIES = 2


def _strip_fences(text: str) -> str:
    """Remove a leading/trailing ```json ... ``` fence if the model added one."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _call_claude(stories: List[Story]) -> List[Story]:
    """Score up to _BATCH_SIZE stories via the `claude` CLI; mutates in-place."""
    payload = [
        {
            "index": i,
            "source": s.source,
            "title": s.title,
            "snippet": s.summary[:600] if s.summary else "",
        }
        for i, s in enumerate(stories)
    ]

    prompt = (
        load_rubric()
        + "\n\n"
        + "Score and summarise the following stories. "
        + "Respond with ONLY a JSON object — no prose, no markdown fences — "
        + 'with this exact shape: {"results": [{"index": <int>, "score": <int>, '
        + '"strand": <str>, "plain_summary": <str>, "content_angle": <str>, '
        + '"how_it_works": <str>}, ...]}\n\n'
        + json.dumps(payload, ensure_ascii=False)
    )

    # Strip any Anthropic API credentials from the child's environment so the
    # CLI always authenticates with the logged-in subscription rather than a
    # (possibly dead) API key that .env/load_dotenv may have set.
    child_env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }

    proc = subprocess.run(
        [_CLAUDE_BIN, "-p", "--model", _MODEL, "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=_CALL_TIMEOUT,
        env=child_env,
    )
    if proc.returncode != 0:
        detail = (proc.stderr.strip() or proc.stdout.strip())[-500:]
        raise RuntimeError(f"claude CLI exited {proc.returncode}: {detail}")

    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI reported error: {envelope.get('result')}")
    text = _strip_fences(envelope["result"])

    try:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # The model sometimes adds prose around the JSON; parse the outermost object.
            data = json.loads(text[text.index("{") : text.rindex("}") + 1])
    except (json.JSONDecodeError, ValueError):
        print(
            f"[scorer] JSON parse failed\n"
            f"  stop_reason={envelope.get('stop_reason')}\n"
            f"  usage={envelope.get('usage')}\n"
            f"  response_text_len={len(text)}\n"
            f"  response_text_tail={text[-200:]!r}"
        )
        raise

    for item in data.get("results", []):
        i = item["index"]
        s = stories[i]
        s.score = item.get("score", 0)
        s.plain_summary = item.get("plain_summary", "")
        s.how_it_works = item.get("how_it_works", "")
        s.content_angle = item.get("content_angle", "")
        strand = str(item.get("strand", "")).strip().lower()
        s.strand = strand if strand in STRANDS else "curiosity"

    return stories


def score_stories(stories: List[Story]) -> List[Story]:
    """Score all stories in place and return them sorted by score desc."""
    for i in range(0, len(stories), _BATCH_SIZE):
        batch = stories[i : i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                _call_claude(batch)
                print(f"[scorer] Scored stories {i + 1}–{min(i + _BATCH_SIZE, len(stories))}")
                break
            except Exception as exc:
                exc_info = f"{type(exc).__name__}: {exc}"
                if attempt < _MAX_RETRIES:
                    print(f"[scorer] Batch {batch_num} attempt {attempt} failed — retrying\n  {exc_info}")
                else:
                    print(f"[scorer] Batch {batch_num} failed after {_MAX_RETRIES} attempts — skipping\n  {exc_info}")
                    print(traceback.format_exc())

    ranked = sorted(stories, key=lambda s: s.score, reverse=True)
    print(f"[scorer] Scored {sum(1 for s in stories if s.score)} of {len(stories)} stories")
    return ranked
