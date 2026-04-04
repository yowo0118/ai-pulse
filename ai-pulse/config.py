import json
import os
from typing import Dict, List, Tuple


CAT_TECH = "\u6280\u672f\u7a81\u7834"
CAT_FUNDING = "\u6295\u878d\u8d44"
CAT_STARTUPS = "\u521b\u4e1a\u516c\u53f8"
CAT_PRODUCT = "\u4ea7\u54c1\u53d1\u5e03"
CAT_INDUSTRY = "\u884c\u4e1a\u52a8\u6001"
CAT_OPEN_SOURCE = "\u5f00\u6e90\u751f\u6001"


RSS_FEEDS: Dict[str, str] = {
    # Core AI Media
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    # AI Lab Blogs
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Anthropic Blog": "https://www.anthropic.com/feed.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Meta AI Blog": "https://ai.meta.com/blog/rss/",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    # AI Influencer Substacks
    "Import AI (Jack Clark)": "https://importai.substack.com/feed",
    "Ahead of AI (Sebastian Raschka)": "https://magazine.sebastianraschka.com/feed",
    "One Useful Thing (Ethan Mollick)": "https://www.oneusefulthing.org/feed",
    "Latent Space": "https://www.latent.space/feed",
    "AI Snake Oil": "https://www.aisnakeoil.com/feed",
    "Semi Analysis": "https://semianalysis.substack.com/feed",
    "Interconnects (Nathan Lambert)": "https://www.interconnects.ai/feed",
    "The Algorithmic Bridge": "https://thealgorithmicbridge.substack.com/feed",
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    # VC / Funding
    "Crunchbase News": "https://news.crunchbase.com/feed/",
    "a16z Blog": "https://a16z.com/feed/",
    "Y Combinator Blog": "https://www.ycombinator.com/blog/rss/",
    # Chinese AI Media
    "\u91cf\u5b50\u4f4d": "https://www.qbitai.com/feed",
    "\u673a\u5668\u4e4b\u5fc3": "https://www.jiqizhixin.com/rss",
}

HN_KEYWORDS: List[str] = [
    "AI",
    "LLM",
    "GPT",
    "Claude",
    "Gemini",
    "OpenAI",
    "Anthropic",
    "machine learning",
    "deep learning",
    "diffusion",
    "fine-tuning",
    "RAG",
    "AGI",
    "DeepSeek",
    "Mistral",
    "Llama",
    "Hugging Face",
    "AI startup",
    "AI funding",
]
HN_MIN_SCORE = 50

REDDIT_SUBREDDITS: List[str] = [
    "MachineLearning",
    "LocalLLaMA",
    "artificial",
    "OpenAI",
    "singularity",
]
REDDIT_MIN_SCORE = 100

CATEGORIES = {
    CAT_TECH: {
        "name_en": "Technical Breakthroughs",
        "emoji": "\U0001F52C",
        "keywords": [
            "breakthrough",
            "sota",
            "new model",
            "benchmark",
            "paper",
            "research",
            "architecture",
            "training",
            "inference",
            "weights",
        ],
    },
    CAT_FUNDING: {
        "name_en": "Funding & Investment",
        "emoji": "\U0001F4B0",
        "keywords": [
            "funding",
            "raised",
            "series",
            "seed",
            "valuation",
            "ipo",
            "acquisition",
            "invest",
            "round",
            "venture",
            "billion",
            "million",
        ],
    },
    CAT_STARTUPS: {
        "name_en": "AI Startups",
        "emoji": "\U0001F680",
        "keywords": [
            "startup",
            "founded",
            "launch",
            "stealth",
            "y combinator",
            "accelerator",
        ],
    },
    CAT_PRODUCT: {
        "name_en": "Product Launches",
        "emoji": "\U0001F4E6",
        "keywords": [
            "launch",
            "release",
            "update",
            "api",
            "beta",
            "preview",
            "announce",
            "ship",
        ],
    },
    CAT_INDUSTRY: {
        "name_en": "Industry Trends",
        "emoji": "\U0001F4CA",
        "keywords": [
            "regulation",
            "policy",
            "ethics",
            "safety",
            "competition",
            "market",
            "trend",
        ],
    },
    CAT_OPEN_SOURCE: {
        "name_en": "Open Source",
        "emoji": "\U0001F310",
        "keywords": [
            "open source",
            "github",
            "repository",
            "community",
            "framework",
            "library",
        ],
    },
}

SCORING_SYSTEM_PROMPT = """
You are an AI industry analyst. Evaluate one news item and return pure JSON only.
No markdown fences, no extra text.

Required JSON schema:
{
  "score_breakdown": {
    "industry_significance": 0-3,
    "novelty": 0-3,
    "practitioner_investor_relevance": 0-2,
    "source_credibility": 0-2
  },
  "total_score": 0-10,
  "category": "\\u6280\\u672f\\u7a81\\u7834|\\u6295\\u878d\\u8d44|\\u521b\\u4e1a\\u516c\\u53f8|\\u4ea7\\u54c1\\u53d1\\u5e03|\\u884c\\u4e1a\\u52a8\\u6001|\\u5f00\\u6e90\\u751f\\u6001",
  "entities": {
    "companies": [],
    "people": [],
    "funding_amounts": [],
    "technologies": []
  },
  "summary_en": "concise summary in English",
  "summary_zh": "\\u7b80\\u6d01\\u4e2d\\u6587\\u6458\\u8981",
  "importance": "high|medium|low"
}

Scoring rules:
- total_score should be the sum of four dimensions (0-10).
- keep the response factual and concise.
"""

SCORING_USER_PROMPT = "Title: {title}\nSource: {source}\nPublished: {published}\nContent: {content}"

OUTPUT_DIR = "output"
MIN_SCORE = 5
MAX_PER_CATEGORY = 10
TIME_WINDOW_HOURS = 24
AI_MODEL = "claude-sonnet-4-20250514"


_SOURCE_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "custom_sources.json")


def _load_source_config() -> Dict[str, object]:
    if not os.path.exists(_SOURCE_CONFIG_FILE):
        return {"added": {}, "removed": []}
    try:
        with open(_SOURCE_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"added": {}, "removed": []}
    if not isinstance(data, dict):
        return {"added": {}, "removed": []}
    added = data.get("added", {})
    removed = data.get("removed", [])
    if not isinstance(added, dict):
        added = {}
    if not isinstance(removed, list):
        removed = []
    clean_added = {str(k): str(v) for k, v in added.items() if str(v).startswith(("http://", "https://"))}
    clean_removed = [str(x) for x in removed]
    return {"added": clean_added, "removed": clean_removed}


def _save_source_config(data: Dict[str, object]) -> None:
    with open(_SOURCE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_rss_feeds() -> Dict[str, str]:
    conf = _load_source_config()
    feeds = dict(RSS_FEEDS)
    for name in conf["removed"]:
        feeds.pop(name, None)
    feeds.update(conf["added"])
    return feeds


def add_rss_source(name: str, url: str) -> Tuple[bool, str]:
    if not name.strip():
        return False, "Source name cannot be empty."
    if not url.startswith(("http://", "https://")):
        return False, "Source URL must start with http:// or https://"

    conf = _load_source_config()
    source_name = name.strip()
    conf["added"][source_name] = url.strip()
    conf["removed"] = [n for n in conf["removed"] if n != source_name]
    _save_source_config(conf)
    return True, f"Added or updated source: {source_name}"


def remove_rss_source(name: str) -> Tuple[bool, str]:
    source_name = name.strip()
    if not source_name:
        return False, "Source name cannot be empty."

    conf = _load_source_config()
    existed_in_added = conf["added"].pop(source_name, None) is not None
    existed_in_base = source_name in RSS_FEEDS

    if existed_in_base and source_name not in conf["removed"]:
        conf["removed"].append(source_name)

    if not existed_in_added and not existed_in_base:
        return False, f"Source not found: {source_name}"

    _save_source_config(conf)
    return True, f"Removed source: {source_name}"


def list_rss_sources() -> List[Dict[str, str]]:
    conf = _load_source_config()
    current = get_rss_feeds()
    out: List[Dict[str, str]] = []
    for name, url in sorted(current.items(), key=lambda x: x[0].lower()):
        if name in conf["added"] and name in RSS_FEEDS:
            state = "overridden"
        elif name in conf["added"]:
            state = "custom"
        else:
            state = "builtin"
        out.append({"name": name, "url": url, "state": state})
    return out
