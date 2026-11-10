"""Fetch and normalise stories from RSS feeds published in the last day."""

import re
import feedparser
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List

FEEDS = {
    "Nature News": "https://www.nature.com/nature.rss",
    "New Scientist": "https://www.newscientist.com/feed/home/",
    "STAT News": "https://www.statnews.com/feed/",
    "BMJ News": "https://news.google.com/rss/search?q=site:bmj.com+news&hl=en-GB&gl=GB&ceid=GB:en",
    "DeepMind Blog": "https://deepmind.google/blog/rss.xml",
    "Google Health Blog": "https://blog.google/technology/health/rss/",
    "The Guardian Science": "https://www.theguardian.com/science/rss",
    "The Guardian Tech": "https://www.theguardian.com/technology/rss",
    "The Guardian AI": "https://www.theguardian.com/technology/artificialintelligenceai/rss",
    "BBC Science & Health": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "The Conversation Health": "https://theconversation.com/uk/health/articles.atom",
    "Longevity Technology": "https://www.longevity.technology/feed/",
    "Algorithm Watch": "https://algorithmwatch.org/en/feed/",
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv q-bio": "https://rss.arxiv.org/rss/q-bio",
    "Quanta Magazine": "https://www.quantamagazine.org/feed/",
    "Science News": "https://www.sciencenews.org/feed",
    "Science (AAAS) News": "https://www.science.org/rss/news_current.xml",
    "Ars Technica Science": "https://feeds.arstechnica.com/arstechnica/science",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    "AI as Normal Technology": "https://www.normaltech.ai/feed",
    "The Conversation Technology": "https://theconversation.com/uk/technology/articles.atom",
    "Our World in Data": "https://ourworldindata.org/atom.xml",
    "arXiv cs.CY": "https://rss.arxiv.org/rss/cs.CY",
    "The Conversation Environment": "https://theconversation.com/uk/environment/articles.atom",
}

CUTOFF_DAYS = 1

@dataclass
class Story:
    title: str
    source: str
    url: str
    summary: str
    published: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: int = 0
    plain_summary: str = ""
    how_it_works: str = ""
    strand: str = ""
    content_angle: str = ""


def _parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


_CONVERSATION_ID = re.compile(r"theconversation\.com/.*?-(\d+)/?(?:[?#].*)?$")


def _dedup_key(story: "Story") -> str:
    """Same story → same key. The Conversation articles are keyed by article ID,
    since they appear in several section feeds."""
    m = _CONVERSATION_ID.search(story.url)
    if m:
        return f"theconversation:{m.group(1)}"
    return story.url if story.url else " ".join(story.title.lower().split())


def fetch_stories(cutoff_days: int = CUTOFF_DAYS) -> List[Story]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
    stories: List[Story] = []

    _ARXIV_SOURCES = {"arXiv cs.AI", "arXiv q-bio", "arXiv cs.CY"}
    _ARXIV_KEYWORDS = {
        "health", "clinical", "medical", "cardiovascular", "disease",
        "fairness", "bias", "patient", "diagnosis", "biomarker",
        "longevity", "cancer", "mental health",
        "interpretability", "explainab", "safety", "alignment", "privacy",
        "evaluation", "contamination", "hallucination", "misinformation",
        "surveillance", "discrimination", "equity", "accountability", "transparency",
    }

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            batch: List[Story] = []
            for entry in feed.entries:
                pub = _parse_date(entry)
                if pub < cutoff:
                    continue
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                summary = (
                    getattr(entry, "summary", "")
                    or getattr(entry, "description", "")
                    or ""
                ).strip()
                if not title or not link:
                    continue
                # Nature's main feed mixes news (d41586 DOIs) with research papers (s41586)
                if source == "Nature News" and "d41586" not in link:
                    continue
                if source in _ARXIV_SOURCES:
                    haystack = (title + " " + summary).lower()
                    if not any(kw in haystack for kw in _ARXIV_KEYWORDS):
                        continue
                batch.append(
                    Story(
                        title=title,
                        source=source,
                        url=link,
                        summary=summary[:1500],
                        published=pub,
                    )
                )
            stories.extend(batch)
        except Exception as exc:
            print(f"[feeds] Failed to fetch {source}: {exc}")

    before = len(stories)
    seen: set = set()
    unique: List[Story] = []
    for s in stories:
        key = _dedup_key(s)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    removed = before - len(unique)
    if removed:
        print(f"[feeds] Removed {removed} duplicate(s) ({before} → {len(unique)})")
    print(f"[feeds] Fetched {len(unique)} stories from the past {cutoff_days} days")
    return unique
