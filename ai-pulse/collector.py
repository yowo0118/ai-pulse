import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Dict, List, Optional

from config import HN_KEYWORDS, HN_MIN_SCORE, REDDIT_MIN_SCORE, REDDIT_SUBREDDITS, TIME_WINDOW_HOURS, get_rss_feeds


USER_AGENT = "AI-Pulse/1.0 (+https://example.com/ai-pulse)"
REQUEST_TIMEOUT = 15


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    parser = _TextExtractor()
    parser.feed(raw)
    text = parser.get_text()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _request_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read()


def _request_json(url: str) -> object:
    raw = _request_url(url)
    return json.loads(raw.decode("utf-8", errors="replace"))


def _parse_datetime(value: str) -> Optional[dt.datetime]:
    if not value:
        return None

    value = value.strip()
    candidates = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M:%S UTC",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    normalized = value.replace("Z", "+0000")
    if re.search(r"[+-]\d{2}:\d{2}$", normalized):
        normalized = normalized[:-3] + normalized[-2:]

    for fmt in candidates:
        try:
            parsed = dt.datetime.strptime(normalized, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except ValueError:
            continue

    m_epoch = re.search(r"\b(\d{10})\b", value)
    if m_epoch:
        try:
            return dt.datetime.fromtimestamp(int(m_epoch.group(1)), tz=dt.timezone.utc)
        except (OSError, ValueError):
            pass

    m_date = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", value)
    if m_date:
        year, month, day = [int(x) for x in m_date.groups()]
        try:
            return dt.datetime(year, month, day, tzinfo=dt.timezone.utc)
        except ValueError:
            return None

    return None


def _extract_atom_link(entry: ET.Element, ns: Dict[str, str]) -> str:
    for link in entry.findall("atom:link", ns):
        href = link.attrib.get("href", "").strip()
        rel = link.attrib.get("rel", "alternate")
        if href and rel in ("alternate", ""):
            return href
    link = entry.find("atom:link", ns)
    if link is not None:
        return link.attrib.get("href", "").strip()
    return ""


def _parse_rss_feed(name: str, url: str, time_window_hours: int) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=time_window_hours)

    try:
        raw = _request_url(url)
        root = ET.fromstring(raw)
    except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError) as exc:
        print(f"[RSS] Failed to fetch {name}: {exc}")
        return items

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }
    root_tag = root.tag.lower()
    is_atom = root_tag.endswith("feed")
    entries = root.findall("atom:entry", ns) if is_atom else root.findall("./channel/item")

    for entry in entries:
        if is_atom:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            link = _extract_atom_link(entry, ns)
            item_id = (entry.findtext("atom:id", default="", namespaces=ns) or link or title).strip()
            content = (
                entry.findtext("atom:content", default="", namespaces=ns)
                or entry.findtext("atom:summary", default="", namespaces=ns)
                or ""
            )
            published_raw = (
                entry.findtext("atom:published", default="", namespaces=ns)
                or entry.findtext("atom:updated", default="", namespaces=ns)
                or ""
            )
        else:
            title = (entry.findtext("title", default="") or "").strip()
            link = (entry.findtext("link", default="") or "").strip()
            item_id = (
                entry.findtext("guid", default="").strip()
                or link
                or title
                or f"{name}-{abs(hash(title))}"
            )
            content = (
                entry.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", default="")
                or entry.findtext("description", default="")
                or ""
            )
            published_raw = (
                entry.findtext("pubDate", default="")
                or entry.findtext("published", default="")
                or entry.findtext("updated", default="")
                or ""
            )

        if not title or not link:
            continue

        published_dt = _parse_datetime(published_raw)
        if published_dt and published_dt < cutoff:
            continue
        if not published_dt:
            published_dt = dt.datetime.now(dt.timezone.utc)

        clean_content = _strip_html(content)[:2000]
        items.append(
            {
                "id": str(item_id),
                "title": title,
                "url": link,
                "source": name,
                "source_type": "rss",
                "content": clean_content,
                "published": published_dt.isoformat(),
                "published_dt": published_dt,
            }
        )
    return items


def fetch_rss_items(time_window_hours: int = TIME_WINDOW_HOURS) -> List[Dict[str, object]]:
    feeds = get_rss_feeds()
    all_items: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_parse_rss_feed, name, url, time_window_hours) for name, url in feeds.items()]
        for future in as_completed(futures):
            try:
                all_items.extend(future.result())
            except Exception as exc:
                print(f"[RSS] Unexpected worker failure: {exc}")
    return all_items


def fetch_hacker_news(time_window_hours: int = TIME_WINDOW_HOURS) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=time_window_hours)

    try:
        story_ids = _request_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"[HN] Failed to fetch top stories: {exc}")
        return out

    if not isinstance(story_ids, list):
        return out

    story_ids = story_ids[:200]
    keyword_lc = [k.lower() for k in HN_KEYWORDS]

    def _fetch_story(story_id: int) -> Optional[Dict[str, object]]:
        try:
            data = _request_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        if data.get("type") != "story":
            return None
        title = str(data.get("title", "")).strip()
        if not title:
            return None
        score = int(data.get("score", 0) or 0)
        if score < HN_MIN_SCORE:
            return None
        lower_title = title.lower()
        if not any(keyword in lower_title for keyword in keyword_lc):
            return None
        ts = data.get("time")
        if not isinstance(ts, int):
            return None
        published_dt = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
        if published_dt < cutoff:
            return None
        text = _strip_html(str(data.get("text", "") or ""))[:2000]
        url = str(data.get("url") or f"https://news.ycombinator.com/item?id={story_id}")
        return {
            "id": f"hn-{story_id}",
            "title": title,
            "url": url,
            "source": "Hacker News",
            "source_type": "hn",
            "content": text,
            "published": published_dt.isoformat(),
            "published_dt": published_dt,
            "hn_score": score,
        }

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_fetch_story, int(sid)) for sid in story_ids if isinstance(sid, int)]
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    out.append(item)
            except Exception:
                continue

    return out


def fetch_reddit(time_window_hours: int = TIME_WINDOW_HOURS) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=time_window_hours)

    for sub in REDDIT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
        try:
            payload = _request_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"[Reddit] Failed for r/{sub}: {exc}")
            time.sleep(1)
            continue

        children = (
            payload.get("data", {}).get("children", [])
            if isinstance(payload, dict)
            else []
        )
        if not isinstance(children, list):
            children = []

        for child in children:
            data = child.get("data", {}) if isinstance(child, dict) else {}
            if not isinstance(data, dict):
                continue
            score = int(data.get("score", 0) or 0)
            if score < REDDIT_MIN_SCORE:
                continue
            created_utc = data.get("created_utc")
            if not isinstance(created_utc, (int, float)):
                continue
            published_dt = dt.datetime.fromtimestamp(float(created_utc), tz=dt.timezone.utc)
            if published_dt < cutoff:
                continue
            permalink = str(data.get("permalink", "") or "")
            post_url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else str(data.get("url", ""))
            title = str(data.get("title", "")).strip()
            if not title or not post_url:
                continue
            content = _strip_html(str(data.get("selftext", "") or ""))[:2000]
            out.append(
                {
                    "id": f"reddit-{sub}-{data.get('id', '')}",
                    "title": title,
                    "url": post_url,
                    "source": f"r/{sub}",
                    "source_type": "reddit",
                    "content": content,
                    "published": published_dt.isoformat(),
                    "published_dt": published_dt,
                    "reddit_score": score,
                }
            )
        time.sleep(1)

    return out


def fetch_github_trending(time_window_hours: int = TIME_WINDOW_HOURS) -> List[Dict[str, object]]:
    del time_window_hours
    topics = ["artificial-intelligence", "machine-learning", "llm", "deep-learning"]
    repo_topics: Dict[str, set] = {}

    for topic in topics:
        url = f"https://github.com/trending/{topic}?since=daily"
        try:
            html = _request_url(url).decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
            print(f"[GitHub] Failed for topic {topic}: {exc}")
            continue
        for match in re.finditer(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', html):
            repo = match.group(1)
            if repo.lower().endswith((".svg", ".png", ".jpg")):
                continue
            repo_topics.setdefault(repo, set()).add(topic)

    now = dt.datetime.now(dt.timezone.utc)
    out: List[Dict[str, object]] = []
    for repo, topic_set in sorted(repo_topics.items()):
        out.append(
            {
                "id": f"github-{repo.replace('/', '-').lower()}",
                "title": repo,
                "url": f"https://github.com/{repo}",
                "source": "GitHub Trending",
                "source_type": "github",
                "content": f"Trending in topics: {', '.join(sorted(topic_set))}. Open source AI repository.",
                "published": now.isoformat(),
                "published_dt": now,
            }
        )
    return out


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url.strip())
    normalized = urllib.parse.urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "",
            "",
        )
    )
    return normalized


def _normalize_title(title: str) -> str:
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", title.lower())
    return text


def deduplicate_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen_urls = set()
    seen_titles = set()
    deduped: List[Dict[str, object]] = []

    for item in items:
        url_key = _normalize_url(str(item.get("url", "")))
        if url_key and url_key in seen_urls:
            continue
        if url_key:
            seen_urls.add(url_key)

        title_key = _normalize_title(str(item.get("title", "")))
        if len(title_key) > 20 and title_key in seen_titles:
            continue
        if len(title_key) > 20:
            seen_titles.add(title_key)

        deduped.append(item)

    return deduped


def collect_all(time_window_hours: int = TIME_WINDOW_HOURS) -> List[Dict[str, object]]:
    tasks = {
        "rss": lambda: fetch_rss_items(time_window_hours=time_window_hours),
        "hn": lambda: fetch_hacker_news(time_window_hours=time_window_hours),
        "reddit": lambda: fetch_reddit(time_window_hours=time_window_hours),
        "github": lambda: fetch_github_trending(time_window_hours=time_window_hours),
    }

    all_items: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(func): name for name, func in tasks.items()}
        for future in as_completed(future_map):
            source_name = future_map[future]
            try:
                data = future.result()
                all_items.extend(data)
                print(f"[Collect] {source_name}: {len(data)} items")
            except Exception as exc:
                print(f"[Collect] {source_name} failed: {exc}")

    deduped = deduplicate_items(all_items)
    deduped.sort(key=lambda x: x.get("published_dt", dt.datetime.min.replace(tzinfo=dt.timezone.utc)), reverse=True)
    return deduped
