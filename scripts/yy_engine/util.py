from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path

UTC = dt.timezone.utc


def utcnow() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso_z(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: object, fallback: dt.datetime | None = None) -> dt.datetime:
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value) / (1000 if value > 10_000_000_000 else 1), UTC)
        except (ValueError, OSError, OverflowError):
            pass
    raw = str(value or "").strip()
    if raw:
        for parser in (
            lambda v: dt.datetime.fromisoformat(v.replace("Z", "+00:00")),
            email.utils.parsedate_to_datetime,
        ):
            try:
                result = parser(raw)
                if result.tzinfo is None:
                    result = result.replace(tzinfo=UTC)
                return result.astimezone(UTC)
            except (TypeError, ValueError, OverflowError):
                continue
    return fallback or dt.datetime(1970, 1, 1, tzinfo=UTC)


def parse_date(value: object, observed_at: dt.datetime | None = None) -> tuple[str, bool]:
    sentinel = dt.datetime(1970, 1, 1, tzinfo=UTC)
    parsed = parse_time(value, sentinel)
    inferred = parsed == sentinel
    return iso_z(observed_at or utcnow()) if inferred else iso_z(parsed), inferred


def clean(value: object, limit: int | None = None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def stable_id(*parts: object, length: int = 20) -> str:
    raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def canonical_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        query = [(k, v) for k, v in query if not k.lower().startswith(("utm_", "ref", "source"))]
        return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urllib.parse.urlencode(query), ""))
    except ValueError:
        return value


def hostname(value: str) -> str:
    try:
        return (urllib.parse.urlsplit(value).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


STOPWORDS = {
    "about", "after", "against", "amid", "before", "being", "could", "from", "have",
    "into", "more", "news", "over", "report", "reports", "said", "says", "that", "their",
    "there", "these", "they", "this", "through", "under", "update", "what", "when", "where",
    "which", "while", "will", "with", "would", "your", "the", "and", "for", "not", "new",
}


def tokens(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9][a-z0-9-]{2,}", value.lower()) if word not in STOPWORDS}


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))

