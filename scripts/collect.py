#!/usr/bin/env python3
"""Zero-cost RSS/Google News collector for FactShecker.

The collector intentionally does not label stories as true/false. It groups
similar headlines and estimates how much *independent public-source support*
is visible in the monitored feeds. Final fact-check verdicts require human
review and evidence inspection.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import feedparser

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "sources" / "sources.json"
DATA_PATH = ROOT / "data" / "index.json"
MAX_ARTICLES = 1200
RETENTION_DAYS = 30
SIMILARITY_THRESHOLD = 0.76
USER_AGENT = "FactShecker/0.1 (+https://github.com/AHDMarwan/FactShecker)"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = unicodedata.normalize("NFKC", value)
    value = value.lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^\w\s\u0600-\u06ff]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()[:20]


def domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower().strip(".")
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def source_profile(domain: str, trusted_sources: list[dict[str, Any]]) -> dict[str, Any]:
    for item in trusted_sources:
        expected = item["domain"].lower().strip(".")
        if domain == expected or domain.endswith("." + expected):
            return {
                "weight": float(item.get("weight", 0.5)),
                "category": item.get("category", "curated"),
                "label": item.get("label", expected),
            }
    return {"weight": 0.35, "category": "unrated", "label": domain or "unknown"}


def google_news_url(feed: dict[str, Any]) -> str:
    query = quote_plus(feed["query"])
    hl = feed.get("hl", "en")
    gl = feed.get("gl", "MA")
    ceid = feed.get("ceid", f"{gl}:{hl}")
    return f"https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"


def feed_url(feed: dict[str, Any]) -> str:
    if feed.get("type") == "google_news":
        return google_news_url(feed)
    return feed["url"]


def entry_time(entry: Any) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", parsed)
    return iso_now()


def origin_from_entry(entry: Any, channel: dict[str, Any]) -> tuple[str, str]:
    source = entry.get("source") or {}
    source_name = clean_text(source.get("title", "")) or channel["name"]
    source_url = source.get("href") or entry.get("link") or feed_url(channel)
    return source_name, source_url


def article_from_entry(entry: Any, channel: dict[str, Any], trusted_sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    title = clean_text(entry.get("title", ""))
    link = entry.get("link", "")
    if not title or not link:
        return None

    source_name, source_url = origin_from_entry(entry, channel)
    domain = domain_of(source_url)
    profile = source_profile(domain, trusted_sources)
    normalized = normalize_text(title)

    return {
        "id": stable_id(normalized, link),
        "title": title,
        "normalized_title": normalized,
        "url": link,
        "published_at": entry_time(entry),
        "language": channel.get("language", "und"),
        "channel": channel["name"],
        "source": {
            "name": source_name,
            "url": source_url,
            "domain": domain,
            "weight": profile["weight"],
            "category": profile["category"],
        },
    }


def collect(config: dict[str, Any]) -> list[dict[str, Any]]:
    articles: dict[str, dict[str, Any]] = {}
    trusted_sources = config.get("trusted_sources", [])

    for channel in config.get("feeds", []):
        if not channel.get("enabled", True):
            continue
        url = feed_url(channel)
        parsed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
        if parsed.bozo and not parsed.entries:
            print(f"warning: feed failed: {channel['name']}: {parsed.bozo_exception}")
            continue

        for entry in parsed.entries[: channel.get("limit", 60)]:
            article = article_from_entry(entry, channel, trusted_sources)
            if article:
                articles[article["id"]] = article

    return list(articles.values())


def load_previous_articles() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        previous = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    articles: dict[str, dict[str, Any]] = {}
    for cluster in previous.get("items", []):
        for article in cluster.get("articles", []):
            if article.get("id"):
                articles[article["id"]] = article
    return list(articles.values())


def parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def retain_recent(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(days=RETENTION_DAYS)
    unique: dict[str, dict[str, Any]] = {}
    for article in articles:
        published = parse_iso(article.get("published_at", ""))
        if published is None or published >= cutoff:
            unique[article["id"]] = article

    ordered = sorted(unique.values(), key=lambda item: item.get("published_at", ""), reverse=True)
    return ordered[:MAX_ARTICLES]


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def is_claim_candidate(title: str) -> bool:
    normalized = normalize_text(title)
    if not normalized or title.rstrip().endswith("?"):
        return False
    indicators = (
        "قال", "أعلن", "أكد", "يزعم", "ينفي", "ارتفع", "انخفض", "منع", "إلغاء",
        "affirme", "annonce", "confirme", "dément", "interdit", "hausse", "baisse",
        "claims", "says", "announces", "confirms", "denies", "bans", "rises", "falls",
    )
    has_number = bool(re.search(r"\d", title))
    return has_number or any(token in normalized for token in indicators)


def cluster_articles(articles: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    representatives: list[str] = []

    for article in articles:
        best_index = -1
        best_score = 0.0
        for index, representative in enumerate(representatives):
            score = similarity(article["normalized_title"], representative)
            if score > best_score:
                best_index = index
                best_score = score
        if best_score >= SIMILARITY_THRESHOLD:
            clusters[best_index].append(article)
        else:
            clusters.append([article])
            representatives.append(article["normalized_title"])
    return clusters


def score_cluster(cluster: list[dict[str, Any]]) -> tuple[float, str]:
    sources = {article["source"]["name"] for article in cluster}
    languages = {article.get("language", "und") for article in cluster}
    weights = [float(article["source"].get("weight", 0.35)) for article in cluster]

    best_source = max(weights, default=0.35)
    corroboration = min(1.0, max(0, len(sources) - 1) / 2)
    language_diversity = min(1.0, max(0, len(languages) - 1) / 2)
    evidence_score = round(0.45 * best_source + 0.45 * corroboration + 0.10 * language_diversity, 3)

    if len(sources) >= 3 and evidence_score >= 0.70:
        status = "corroborated"
    elif len(sources) >= 2:
        status = "medium_evidence"
    else:
        status = "needs_review"
    return evidence_score, status


def build_index(articles: list[dict[str, Any]]) -> dict[str, Any]:
    clusters = cluster_articles(articles)
    items: list[dict[str, Any]] = []

    for cluster in clusters:
        cluster = sorted(cluster, key=lambda item: item.get("published_at", ""), reverse=True)
        representative = cluster[0]
        evidence_score, status = score_cluster(cluster)
        sources = sorted({article["source"]["name"] for article in cluster})
        languages = sorted({article.get("language", "und") for article in cluster})
        claim_candidate = any(is_claim_candidate(article["title"]) for article in cluster)

        items.append({
            "id": stable_id(*(article["id"] for article in cluster[:8])),
            "title": representative["title"],
            "published_at": representative["published_at"],
            "status": status,
            "evidence_score": evidence_score,
            "claim_candidate": claim_candidate,
            "source_count": len(sources),
            "article_count": len(cluster),
            "sources": sources,
            "languages": languages,
            "articles": cluster,
        })

    items.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    statuses = Counter(item["status"] for item in items)
    unique_sources = {article["source"]["name"] for article in articles}

    return {
        "generated_at": iso_now(),
        "methodology_version": "0.1",
        "notice": "Evidence-support score only; not an automated truth verdict.",
        "stats": {
            "articles": len(articles),
            "clusters": len(items),
            "sources": len(unique_sources),
            "needs_review": statuses.get("needs_review", 0),
            "medium_evidence": statuses.get("medium_evidence", 0),
            "corroborated": statuses.get("corroborated", 0),
        },
        "items": items,
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    fresh = collect(config)
    previous = load_previous_articles()
    retained = retain_recent(previous + fresh)
    index = build_index(retained)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
