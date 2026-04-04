import copy
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

from config import CAT_INDUSTRY, AI_MODEL, CATEGORIES, MIN_SCORE, SCORING_SYSTEM_PROMPT, SCORING_USER_PROMPT


USER_AGENT = "AI-Pulse/1.0 (+https://example.com/ai-pulse)"
REQUEST_TIMEOUT = 15

KNOWN_AI_COMPANIES = [
    "OpenAI",
    "Anthropic",
    "Google",
    "DeepMind",
    "Meta",
    "Microsoft",
    "Amazon",
    "NVIDIA",
    "xAI",
    "Mistral",
    "Cohere",
    "Perplexity",
    "Hugging Face",
    "Databricks",
    "Scale AI",
    "Midjourney",
    "Runway",
    "Adept",
    "Character.AI",
    "Stability AI",
    "Inflection AI",
    "Safe Superintelligence",
    "Figure",
    "Glean",
    "Harvey",
    "DeepSeek",
    "Moonshot AI",
    "MiniMax",
    "Zhipu AI",
    "01.AI",
    "Alibaba",
    "Tencent",
    "Baidu",
    "ByteDance",
    "Y Combinator",
    "a16z",
    "Sequoia",
]

TECH_TERMS = [
    "LLM",
    "RAG",
    "fine-tuning",
    "inference",
    "diffusion",
    "transformer",
    "MoE",
    "agent",
    "reasoning model",
    "multimodal",
    "SOTA",
    "benchmark",
    "alignment",
    "safety",
    "quantization",
    "RLHF",
    "distillation",
    "LoRA",
    "vLLM",
    "OpenWeights",
    "tokenizer",
    "embedding",
    "vector database",
    "MCP",
]

FUNDING_PATTERNS = [
    re.compile(r"\$\s?\d+(?:\.\d+)?\s?(?:billion|million|B|M)\b", re.IGNORECASE),
    re.compile(r"raised\s+\$?\s?\d+(?:\.\d+)?\s?(?:billion|million|B|M)?", re.IGNORECASE),
    re.compile(r"series\s+[A-Z]\b", re.IGNORECASE),
]

SUMMARY_SYSTEM_PROMPT = """
You are a concise AI news analyst.
Return JSON only:
{
  "summary_en": "1-2 sentence English summary",
  "summary_zh": "1-2 sentence Chinese summary"
}
Focus on what happened, why it matters, and avoid hype.
"""


def _strip_markdown_code_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_json_block(text: str) -> Dict[str, object]:
    cleaned = _strip_markdown_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise json.JSONDecodeError("No JSON object found", cleaned, 0)


def _derive_category(title: str, content: str) -> str:
    text = f"{title} {content}".lower()
    best = (CAT_INDUSTRY, 0)
    for category, meta in CATEGORIES.items():
        score = sum(1 for kw in meta["keywords"] if kw.lower() in text)
        if score > best[1]:
            best = (category, score)
    return best[0]


def _extract_entities(title: str, content: str) -> Dict[str, List[str]]:
    text = f"{title} {content}"
    text_lc = text.lower()

    companies = [name for name in KNOWN_AI_COMPANIES if name.lower() in text_lc]
    tech = [term for term in TECH_TERMS if term.lower() in text_lc]

    funding = []
    for pattern in FUNDING_PATTERNS:
        for match in pattern.findall(text):
            funding.append(match.strip())

    seen = set()
    funding_clean = []
    for amount in funding:
        key = amount.lower()
        if key in seen:
            continue
        seen.add(key)
        funding_clean.append(amount)

    return {
        "companies": companies[:10],
        "people": [],
        "funding_amounts": funding_clean[:10],
        "technologies": tech[:15],
    }


def _importance_from_score(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def _keyword_score_item(item: Dict[str, object]) -> Dict[str, object]:
    scored = copy.deepcopy(item)
    title = str(scored.get("title", ""))
    content = str(scored.get("content", ""))
    source = str(scored.get("source", ""))
    text = f"{title} {content}".lower()

    base = 4.0

    all_keywords = []
    for meta in CATEGORIES.values():
        all_keywords.extend(meta["keywords"])
    matched_keywords = {kw.lower() for kw in all_keywords if kw.lower() in text}
    keyword_bonus = min(7.0, 0.8 * len(matched_keywords))

    source_boost = 0.0
    source_lc = source.lower()
    if any(k in source_lc for k in ("openai", "anthropic", "deepmind")):
        source_boost += 2.0
    elif any(k in source_lc for k in ("meta ai", "hugging face")):
        source_boost += 1.5
    elif "techcrunch" in source_lc:
        source_boost += 1.0

    has_funding = any(pattern.search(f"{title} {content}") for pattern in FUNDING_PATTERNS)
    funding_bonus = 1.5 if has_funding else 0.0

    launch_signals = ("launch", "release", "announc", "beta", "preview", "ship", "api")
    launch_bonus = 0.5 if any(sig in text for sig in launch_signals) else 0.0

    hn_score = float(scored.get("hn_score", 0) or 0)
    reddit_score = float(scored.get("reddit_score", 0) or 0)
    social_bonus = 0.0
    if hn_score > 500 or reddit_score > 2000:
        social_bonus = 2.0
    elif hn_score > 200 or reddit_score > 500:
        social_bonus = 1.0

    open_source_bonus = 0.0
    if any(sig in text for sig in ("open source", "github", "repository", "apache-2.0", "mit license")):
        open_source_bonus = 0.5

    final_score = min(10.0, base + keyword_bonus + source_boost + funding_bonus + launch_bonus + social_bonus + open_source_bonus)
    final_score = round(final_score, 1)

    category = _derive_category(title, content)
    entities = _extract_entities(title, content)
    importance = _importance_from_score(final_score)

    scored.update(
        {
            "score": final_score,
            "score_breakdown": {
                "industry_significance": min(3, int(final_score // 3)),
                "novelty": min(3, int((final_score - 1) // 3)),
                "practitioner_investor_relevance": 2 if final_score >= 7 else 1,
                "source_credibility": 2 if source_boost >= 1 else 1,
            },
            "category": category,
            "entities": entities,
            "summary_en": f"{title} ({source}) highlights a notable AI development with score {final_score}.",
            "summary_zh": f"{source} \u62a5\u9053\uff1a{title}\uff0c\u7efc\u5408\u8bc4\u5206 {final_score}\uff0c\u503c\u5f97\u5173\u6ce8\u3002",
            "importance": importance,
            "scoring_mode": "keyword",
        }
    )
    return scored


def _post_json(url: str, payload: Dict[str, object], headers: Dict[str, str]) -> Dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _call_anthropic(item: Dict[str, object]) -> Dict[str, object]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    prompt = SCORING_USER_PROMPT.format(
        title=item.get("title", ""),
        source=item.get("source", ""),
        published=item.get("published", ""),
        content=item.get("content", ""),
    )
    payload = {
        "model": AI_MODEL,
        "max_tokens": 500,
        "system": SCORING_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            result = _post_json("https://api.anthropic.com/v1/messages", payload, headers)
            content_blocks = result.get("content", [])
            if not isinstance(content_blocks, list):
                raise ValueError("Invalid Anthropic response: content is not a list")
            text_parts = [block.get("text", "") for block in content_blocks if isinstance(block, dict)]
            return _extract_json_block("\n".join(text_parts))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            break
    if last_exc:
        raise last_exc
    raise RuntimeError("Anthropic call failed without details.")


def _call_openai(item: Dict[str, object]) -> Dict[str, object]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = SCORING_USER_PROMPT.format(
        title=item.get("title", ""),
        source=item.get("source", ""),
        published=item.get("published", ""),
        content=item.get("content", ""),
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    result = _post_json("https://api.openai.com/v1/chat/completions", payload, headers)
    choices = result.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise ValueError("Invalid OpenAI response: missing choices")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    return _extract_json_block(str(content))


def _call_openai_summary(item: Dict[str, object]) -> Dict[str, object]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_SUMMARY_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    content = str(item.get("content", ""))[:1800]
    user_prompt = (
        f"Title: {item.get('title', '')}\n"
        f"Source: {item.get('source', '')}\n"
        f"Published: {item.get('published', '')}\n"
        f"Content: {content}"
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 220,
        "messages": [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            result = _post_json("https://api.openai.com/v1/chat/completions", payload, headers)
            choices = result.get("choices", [])
            if not isinstance(choices, list) or not choices:
                raise ValueError("Invalid OpenAI summary response: missing choices")
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            raw_text = str(message.get("content", "")) if isinstance(message, dict) else ""
            return _extract_json_block(raw_text)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            break
    if last_exc:
        raise last_exc
    raise RuntimeError("OpenAI summary call failed without details.")


def _normalize_ai_output(item: Dict[str, object], ai_data: Dict[str, object], provider: str) -> Dict[str, object]:
    scored = copy.deepcopy(item)
    breakdown = ai_data.get("score_breakdown", {})
    if not isinstance(breakdown, dict):
        breakdown = {}

    if "total_score" in ai_data:
        raw_score = float(ai_data.get("total_score") or 0)
    elif "score" in ai_data:
        raw_score = float(ai_data.get("score") or 0)
    else:
        raw_score = float(
            breakdown.get("industry_significance", 0)
            + breakdown.get("novelty", 0)
            + breakdown.get("practitioner_investor_relevance", 0)
            + breakdown.get("source_credibility", 0)
        )
    score = round(max(0.0, min(10.0, raw_score)), 1)

    category = str(ai_data.get("category", "")).strip()
    if category not in CATEGORIES:
        category = _derive_category(str(scored.get("title", "")), str(scored.get("content", "")))

    entities = ai_data.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}
    fallback_entities = _extract_entities(str(scored.get("title", "")), str(scored.get("content", "")))
    for key in ("companies", "people", "funding_amounts", "technologies"):
        if not isinstance(entities.get(key), list):
            entities[key] = fallback_entities.get(key, [])

    summary_en = str(ai_data.get("summary_en", "")).strip() or f"{scored.get('title', '')}"
    summary_zh = str(ai_data.get("summary_zh", "")).strip() or f"{scored.get('title', '')}"
    importance = str(ai_data.get("importance", "")).strip().lower()
    if importance not in ("high", "medium", "low"):
        importance = _importance_from_score(score)

    scored.update(
        {
            "score": score,
            "score_breakdown": {
                "industry_significance": float(breakdown.get("industry_significance", 0)),
                "novelty": float(breakdown.get("novelty", 0)),
                "practitioner_investor_relevance": float(breakdown.get("practitioner_investor_relevance", 0)),
                "source_credibility": float(breakdown.get("source_credibility", 0)),
            },
            "category": category,
            "entities": entities,
            "summary_en": summary_en,
            "summary_zh": summary_zh,
            "importance": importance,
            "scoring_mode": provider,
        }
    )
    return scored


def score_items(items: List[Dict[str, object]], use_ai: bool = True, min_score: int = MIN_SCORE) -> List[Dict[str, object]]:
    scored_items: List[Dict[str, object]] = []
    use_anthropic = use_ai and bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    use_openai = use_ai and (not use_anthropic) and bool(os.getenv("OPENAI_API_KEY", "").strip())
    provider = "anthropic" if use_anthropic else ("openai" if use_openai else "keyword")

    for idx, item in enumerate(items, start=1):
        try:
            if provider == "anthropic":
                ai_data = _call_anthropic(item)
                scored = _normalize_ai_output(item, ai_data, provider="anthropic")
                time.sleep(0.5)
            elif provider == "openai":
                ai_data = _call_openai(item)
                scored = _normalize_ai_output(item, ai_data, provider="openai")
                time.sleep(0.5)
            else:
                scored = _keyword_score_item(item)
        except Exception as exc:
            print(f"[Score] Item {idx} failed in AI mode, fallback to keyword: {exc}")
            scored = _keyword_score_item(item)

        if float(scored.get("score", 0)) >= min_score:
            scored_items.append(scored)

    scored_items.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return scored_items


def enrich_summaries_with_chatgpt(items: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], int]:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return items, 0

    updated: List[Dict[str, object]] = []
    success = 0
    for idx, item in enumerate(items, start=1):
        enriched = copy.deepcopy(item)
        try:
            summary_data = _call_openai_summary(item)
            summary_en = str(summary_data.get("summary_en", "")).strip()
            summary_zh = str(summary_data.get("summary_zh", "")).strip()
            if summary_en:
                enriched["summary_en"] = summary_en
            if summary_zh:
                enriched["summary_zh"] = summary_zh
            if summary_en or summary_zh:
                success += 1
            enriched["summary_model"] = os.getenv("OPENAI_SUMMARY_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
            time.sleep(0.5)
        except Exception as exc:
            print(f"[Summary] Item {idx} ChatGPT summary failed, keep fallback summary: {exc}")
        updated.append(enriched)
    return updated, success
