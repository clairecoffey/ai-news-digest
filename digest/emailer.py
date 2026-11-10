"""Send the daily digest via Resend."""

import os
from datetime import datetime
from typing import Dict, List
import resend
from digest.feeds import FEEDS, Story
from digest.scorer import STRANDS

# Name shown in the email heading and subject line. Override with DIGEST_TITLE.
_TITLE = os.environ.get("DIGEST_TITLE", "AI & Science Daily")


def _story_html(s: Story, rank: int) -> str:
    score_bar = "●" * s.score + "○" * (10 - s.score)
    return f"""
<div style="margin-bottom:32px;padding:20px;border-left:4px solid #2563eb;background:#f8fafc;border-radius:0 8px 8px 0;">
  <p style="margin:0 0 4px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">
    #{rank} &nbsp;·&nbsp; {s.source} &nbsp;·&nbsp; Score: {s.score}/10 &nbsp; <span style="color:#2563eb;font-family:monospace">{score_bar}</span>
  </p>
  <h2 style="margin:0 0 8px;font-size:17px;line-height:1.4;">
    <a href="{s.url}" style="color:#1e293b;text-decoration:none;">{s.title}</a>
  </h2>
  <p style="margin:0 0 8px;font-size:15px;color:#1e293b;line-height:1.6;"><strong>{s.plain_summary}</strong></p>
  <p style="margin:0 0 8px;font-size:14px;color:#334155;line-height:1.6;">
    <em>The angle:</em> {s.content_angle}
  </p>
  <p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">
    <em>How it works:</em> {s.how_it_works}
  </p>
</div>
"""


def build_html(groups: Dict[str, List[Story]]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    total = sum(len(g) for g in groups.values())
    story_blocks = ""
    rank = 1
    for strand, group in groups.items():
        story_blocks += (
            f'<h2 style="margin:40px 0 16px;font-size:13px;color:#2563eb;text-transform:uppercase;'
            f'letter-spacing:.08em;">{STRANDS.get(strand, strand)} ({len(group)})</h2>'
        )
        for s in group:
            story_blocks += _story_html(s, rank)
            rank += 1
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{_TITLE} — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:32px 24px;">
    <div style="border-bottom:2px solid #2563eb;padding-bottom:16px;margin-bottom:32px;">
      <h1 style="margin:0 0 4px;font-size:24px;color:#1e293b;">{_TITLE}</h1>
      <p style="margin:0;font-size:14px;color:#64748b;">{date_str} &nbsp;·&nbsp; {total} stories curated for a general audience</p>
    </div>
    {story_blocks}
    <div style="border-top:1px solid #e2e8f0;padding-top:16px;margin-top:16px;font-size:12px;color:#94a3b8;text-align:center;">
      Stories scored by Claude from {len(FEEDS)} RSS feeds.
    </div>
  </div>
</body>
</html>"""


def send_digest(groups: Dict[str, List[Story]]) -> None:
    total = sum(len(g) for g in groups.values())
    if not total:
        print("[emailer] No stories to send — skipping email")
        return

    resend.api_key = os.environ["RESEND_API_KEY"]
    from_email = os.environ.get("FROM_EMAIL", "digest@yourdomain.com")
    to_email = os.environ["TO_EMAIL"]

    date_str = datetime.now().strftime("%B %d")
    subject = f"{_TITLE} — {date_str} ({total} stories)"

    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": build_html(groups),
    }

    result = resend.Emails.send(params)
    print(f"[emailer] Sent digest with {total} stories → {to_email} (id: {result.get('id', '?')})")
