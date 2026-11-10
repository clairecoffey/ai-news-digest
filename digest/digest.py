"""Orchestrate the full digest pipeline."""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv
from digest.feeds import Story, fetch_stories
from digest.scorer import STRANDS, score_stories
from digest.emailer import send_digest

_ARCHIVE_DIR = Path(__file__).resolve().parent.parent / "digests"
# A strand with nothing in the top N still gets its best story if it scores at least this.
_STRAND_FLOOR = 6


def select_stories(ranked: List[Story], min_score: int, top_n: int) -> List[Story]:
    """Top N stories at or above min_score, plus the best story from any missing strand."""
    chosen = [s for s in ranked if s.score >= min_score][:top_n]
    for strand in STRANDS:
        if any(s.strand == strand for s in chosen):
            continue
        best = next((s for s in ranked if s.strand == strand and s.score >= _STRAND_FLOOR), None)
        if best:
            chosen.append(best)
    return chosen


def group_by_strand(stories: List[Story]) -> Dict[str, List[Story]]:
    """Group stories by strand; sections ordered by their best score, stories by score."""
    groups: Dict[str, List[Story]] = {}
    for s in sorted(stories, key=lambda s: s.score, reverse=True):
        groups.setdefault(s.strand, []).append(s)
    return groups


def save_markdown(stories: List[Story]) -> Path:
    _ARCHIVE_DIR.mkdir(exist_ok=True)
    path = _ARCHIVE_DIR / f"{datetime.now():%Y-%m-%d}.md"
    lines = [f"# AI & Science Daily — {datetime.now():%d %B %Y}", "", f"{len(stories)} stories", ""]
    for strand, group in group_by_strand(stories).items():
        lines += [f"## {STRANDS.get(strand, strand)}", ""]
        for s in group:
            lines += [
                f"### [{s.title}]({s.url})",
                f"*{s.source} · {s.score}/10 · `{s.strand}`*",
                "",
                f"**Summary:** {s.plain_summary}",
                "",
                f"**Angle:** {s.content_angle}",
                "",
                f"**How it works:** {s.how_it_works}",
                "",
            ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run(dry_run: bool = False) -> None:
    load_dotenv()

    min_score = int(os.environ.get("MIN_SCORE", "7"))
    top_n = int(os.environ.get("TOP_N", "12"))

    stories = fetch_stories()
    ranked = score_stories(stories)
    top = select_stories(ranked, min_score=min_score, top_n=top_n)

    print(f"[digest] Final selection: {len(top)} stories")
    for strand, group in group_by_strand(top).items():
        print(f"  {STRANDS.get(strand, strand)}")
        for s in group:
            print(f"    [{s.score}/10] {s.title[:80]}")

    if top:
        print(f"[digest] Saved {save_markdown(top)}")

    if dry_run:
        print("[digest] Dry-run mode — email not sent")
    else:
        send_digest(group_by_strand(top))
