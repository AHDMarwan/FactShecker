#!/usr/bin/env python3
"""Zero-cost RSS/Google News collector for FactShecker.

The collector intentionally does not label stories as true/false. It groups
similar headlines, estimates how much *independent public-source support* is
visible in monitored feeds, and separately surfaces textually related items
from known fact-checking sources. Final verdicts require human review.
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
FACT_CHECK_MATCH_THRESHOLD = 0.46
MAX_FACT_CHECK_MATCHES = 3
USER_AGENT = "FactShecker/0.2 (+https://github.com/AHDMarwan/FactShecker)"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
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


def strip_publisher_suffix(title: str, source_name: str = "") -> str:
    """Remove common Google News publisher suffixes without rewriting headlines."""
    title = clean_text(title)
    source_name = clean_text(source_name)
    if source_name:
        suffix = f" - {source_name}"
        if title.casefold().endswith(suffix.casefold()):
            return title[: -len(suffix)].rstrip()

    # Safe fallback for domain-like suffixes: "Headline - example.com".
    return re.sub(r"\s+-\s+[\w.-]+\.[a-z]{2,}$", "", title, flags=re.IGNORECASE).strip()


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
    raw_title = clean_text(entry.get("title", ""))
    link = entry.get("link", "")
    if not raw_title or not link:
        return None

    source_name, source_url = origin_from_entry(entry, channel)
    title = strip_publisher_suffix(raw_title, source_name)
    domain = domain_of(source_url)
    profile = source_profile(domain, trusted_sources)
    normalized = normalize_text(title)

    return {
        "id": stable_id(normalized, link),
        "title": title,
        "raw_title": raw_title,
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
    for article in previous.get("fact_checks", []):
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


def token_jaccard(a: str, b: str) -> float:
    tokens_a = {token for token in normalize_text(a).split() if len(token) > 1}
    tokens_b = {token for token in normalize_text(b).split() if len(token) > 1}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def claim_features(title: str) -> dict[str, Any]:
    """Heuristic check-worthiness signals; this is not a truth classifier."""
    title = strip_publisher_suffix(title)
    normalized = normalize_text(title)
    reasons: list[str] = []
    if not normalized:
        return {"candidate": False, "score": 0.0, "reasons": ["empty"]}

    if title.rstrip().endswith(("?", "؟")):
        return {"candidate": False, "score": 0.0, "reasons": ["question"]}

    score = 0.0
    tokens = normalized.split()
    if len(tokens) >= 5:
        score += 0.10
        reasons.append("specific_statement")

    reporting_indicators = (
        "قال", "اعلن", "اكد", "يزعم", "ينفي", "نفى", "صرح", "قرر", "سجل", "بلغ",
        "affirme", "annonce", "confirme", "dement", "declare", "decide", "atteint",
        "claims", "says", "announces", "confirms", "denies", "declares", "decides", "reaches",
    )
    event_indicators = (
        "ارتفع", "انخفض", "منع", "الغاء", "ا لغاء", "توقف", "افتتاح", "اطلاق",
        "hausse", "baisse", "interdit", "annule", "lance",
        "rises", "falls", "bans", "cancels", "launches",
    )
    opinion_indicators = (
        "راي", "تحليل", "لماذا", "كيف يمكن", "وجهة نظر",
        "opinion", "analyse", "pourquoi", "chronique",
        "analysis", "why", "commentary", "editorial",
    )

    if any(token in normalized for token in reporting_indicators):
        score += 0.30
        reasons.append("reported_assertion")
    if any(token in normalized for token in event_indicators):
        score += 0.20
        reasons.append("event_assertion")
    if re.search(r"\d", title):
        score += 0.25
        reasons.append("numeric_detail")
    if re.search(r"[%٪$€£]|\b(?:dh|mad|usd|eur)\b", title, flags=re.IGNORECASE):
        score += 0.10
        reasons.append("quantified_value")
    if any(token in normalized for token in opinion_indicators):
        score -= 0.35
        reasons.append("opinion_or_analysis")

    score = round(max(0.0, min(1.0, score)), 3)
    return {"candidate": score >= 0.35, "score": score, "reasons": reasons}


def is_claim_candidate(title: str) -> bool:
    return bool(claim_features(title)["candidate"])


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


def support_articles(cluster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [article for article in cluster if article.get("source", {}).get("category") != "fact_checker"]


def score_cluster(cluster: list[dict[str, Any]]) -> tuple[float, str]:
    supporting = support_articles(cluster)
    sources = {article["source"]["name"] for article in supporting}
    languages = {article.get("language", "und") for article in supporting}
    weights = [float(article["source"].get("weight", 0.35)) for article in supporting]

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


def fact_check_similarity(claim_title: str, fact_check_title: str, same_language: bool = False) -> float:
    a = normalize_text(strip_publisher_suffix(claim_title))
    b = normalize_text(strip_publisher_suffix(fact_check_title))
    if not a or not b:
        return 0.0
    seq = similarity(a, b)
    overlap = token_jaccard(a, b)
    score = 0.45 * seq + 0.55 * overlap
    if same_language:
        score += 0.05
    return round(min(1.0, score), 3)


def match_fact_checks(
    cluster: list[dict[str, Any]],
    fact_checks: list[dict[str, Any]],
    limit: int = MAX_FACT_CHECK_MATCHES,
) -> list[dict[str, Any]]:
    if not cluster or not fact_checks:
        return []

    representative = cluster[0]
    matches: list[dict[str, Any]] = []
    for fact_check in fact_checks:
        same_language = representative.get("language") == fact_check.get("language")
        score = fact_check_similarity(representative["title"], fact_check["title"], same_language)
        if score < FACT_CHECK_MATCH_THRESHOLD:
            continue
        matches.append({
            "id": fact_check["id"],
            "title": fact_check["title"],
            "url": fact_check["url"],
            "published_at": fact_check.get("published_at"),
            "language": fact_check.get("language", "und"),
            "source": fact_check.get("source", {}),
            "similarity": score,
        })

    matches.sort(key=lambda item: (item["similarity"], item.get("published_at") or ""), reverse=True)
    return matches[:limit]


def build_index(articles: list[dict[str, Any]]) -> dict[str, Any]:
    fact_checks = [
        article for article in articles
        if article.get("source", {}).get("category") == "fact_checker"
    ]
    news_articles = [
        article for article in articles
        if article.get("source", {}).get("category") != "fact_checker"
    ]

    clusters = cluster_articles(news_articles)
    items: list[dict[str, Any]] = []

    for cluster in clusters:
        cluster = sorted(cluster, key=lambda item: item.get("published_at", ""), reverse=True)
        representative = cluster[0]
        evidence_score, status = score_cluster(cluster)
        sources = sorted({article["source"]["name"] for article in cluster})
        languages = sorted({article.get("language", "und") for article in cluster})
        claim = max((claim_features(article["title"]) for article in cluster), key=lambda item: item["score"])
        fact_check_matches = match_fact_checks(cluster, fact_checks)

        items.append({
            "id": stable_id(*(article["id"] for article in cluster[:8])),
            "title": representative["title"],
            "published_at": representative["published_at"],
            "status": status,
            "evidence_score": evidence_score,
            "claim_candidate": claim["candidate"],
            "claim_score": claim["score"],
            "claim_reasons": claim["reasons"],
            "fact_check_matches": fact_check_matches,
            "source_count": len(sources),
            "article_count": len(cluster),
            "sources": sources,
            "languages": languages,
            "articles": cluster,
        })

    items.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    fact_checks.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    statuses = Counter(item["status"] for item in items)
    unique_sources = {article["source"]["name"] for article in articles}
    matched_clusters = sum(bool(item["fact_check_matches"]) for item in items)

    return {
        "generated_at": iso_now(),
        "methodology_version": "0.2",
        "notice": "Evidence-support and text-match signals only; not an automated truth verdict.",
        "stats": {
            "records": len(articles),
            "articles": len(news_articles),
            "fact_checks": len(fact_checks),
            "clusters": len(items),
            "sources": len(unique_sources),
            "matched_clusters": matched_clusters,
            "needs_review": statuses.get("needs_review", 0),
            "medium_evidence": statuses.get("medium_evidence", 0),
            "corroborated": statuses.get("corroborated", 0),
        },
        "fact_checks": fact_checks[:250],
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
