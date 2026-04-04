import datetime as dt
import json
import os
from typing import Dict, List, Tuple

from config import CAT_INDUSTRY, CATEGORIES, MAX_PER_CATEGORY, OUTPUT_DIR


def _ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _clean_item(item: Dict[str, object]) -> Dict[str, object]:
    clean = dict(item)
    pd = clean.get("published_dt")
    if hasattr(pd, "isoformat"):
        clean["published_dt"] = pd.isoformat()
    return clean


def _indicator(score: float) -> str:
    if score >= 8:
        return "\U0001F7E2"
    if score >= 5:
        return "\U0001F7E1"
    return "\u26AA"


def _build_stats(items: List[Dict[str, object]]) -> Dict[str, int]:
    total = len(items)
    high = sum(1 for x in items if x.get("importance") == "high")
    medium = sum(1 for x in items if x.get("importance") == "medium")
    categories_covered = len({x.get("category", "") for x in items if x.get("category") in CATEGORIES})
    return {
        "total_items": total,
        "high_importance": high,
        "medium_importance": medium,
        "categories_covered": categories_covered,
    }


def generate_reports(items: List[Dict[str, object]], output_dir: str = OUTPUT_DIR) -> Tuple[str, str]:
    _ensure_output_dir(output_dir)
    now = dt.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    generated_at = now.isoformat(timespec="seconds")

    sorted_items = sorted(items, key=lambda x: float(x.get("score", 0)), reverse=True)
    top_stories = [x for x in sorted_items if float(x.get("score", 0)) >= 8][:5]

    grouped: Dict[str, List[Dict[str, object]]] = {k: [] for k in CATEGORIES.keys()}
    for item in sorted_items:
        category = item.get("category", CAT_INDUSTRY)
        if category not in grouped:
            category = CAT_INDUSTRY
        grouped[category].append(item)
    for cat in grouped:
        grouped[cat] = grouped[cat][:MAX_PER_CATEGORY]

    stats = _build_stats(sorted_items)

    md_lines: List[str] = []
    md_lines.append("# \U0001F916 AI Pulse Daily Briefing")
    md_lines.append("")
    md_lines.append(f"- Date: `{date_str}`")
    md_lines.append(f"- Generated At: `{generated_at}`")
    md_lines.append("")
    md_lines.append("## Summary")
    md_lines.append(f"- Total Items: **{stats['total_items']}**")
    md_lines.append(f"- High Importance: **{stats['high_importance']}**")
    md_lines.append(f"- Medium Importance: **{stats['medium_importance']}**")
    md_lines.append(f"- Categories Covered: **{stats['categories_covered']} / {len(CATEGORIES)}**")
    md_lines.append("")
    md_lines.append("## Table of Contents")
    for idx, (cat, meta) in enumerate(CATEGORIES.items(), start=1):
        count = len(grouped.get(cat, []))
        md_lines.append(f"- [{meta['emoji']} {cat} / {meta['name_en']} ({count})](#cat-{idx})")
    md_lines.append("")
    md_lines.append("## \U0001F525 Top Stories / \u4eca\u65e5\u5934\u6761")
    if top_stories:
        for item in top_stories:
            score = float(item.get("score", 0))
            cat = item.get("category", CAT_INDUSTRY)
            meta = CATEGORIES.get(cat, CATEGORIES[CAT_INDUSTRY])
            entities = item.get("entities", {}) if isinstance(item.get("entities"), dict) else {}
            companies = ", ".join(entities.get("companies", [])[:3]) if isinstance(entities.get("companies"), list) else ""
            funding = ", ".join(entities.get("funding_amounts", [])[:2]) if isinstance(entities.get("funding_amounts"), list) else ""
            info_parts = [f"Score `{score}`", f"{meta['emoji']} {cat}", str(item.get("source", ""))]
            if companies:
                info_parts.append(f"Companies: {companies}")
            if funding:
                info_parts.append(f"Funding: {funding}")
            md_lines.append(f"- **[{item.get('title','')}]({item.get('url','')})**")
            md_lines.append(f"  - {' | '.join(info_parts)}")
            md_lines.append(f"  - EN: {item.get('summary_en', '')}")
            md_lines.append(f"  - ZH: {item.get('summary_zh', '')}")
    else:
        md_lines.append("- No top stories with score >= 8 today.")
    md_lines.append("")

    for idx, (cat, meta) in enumerate(CATEGORIES.items(), start=1):
        md_lines.append(f'<a id="cat-{idx}"></a>')
        md_lines.append(f"## {meta['emoji']} {cat} / {meta['name_en']} ({len(grouped.get(cat, []))})")
        if not grouped.get(cat):
            md_lines.append("- No items in this category.")
            md_lines.append("")
            continue
        for item in grouped[cat]:
            score = float(item.get("score", 0))
            marker = _indicator(score)
            md_lines.append(
                f"- {marker} **[{item.get('title', '')}]({item.get('url', '')})**"
                f" | Score `{score}` | Source `{item.get('source', '')}` | Date `{item.get('published', '')}`"
            )
            md_lines.append(f"  - EN: {item.get('summary_en', '')}")
            md_lines.append(f"  - ZH: {item.get('summary_zh', '')}")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append(f"Generated by AI Pulse at `{generated_at}`")
    md_content = "\n".join(md_lines)

    md_path = os.path.join(output_dir, f"ai-pulse-{date_str}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    json_data = {
        "date": date_str,
        "generated_at": generated_at,
        "stats": stats,
        "top_stories": [_clean_item(x) for x in top_stories],
        "categories": {
            cat: {
                "name_en": CATEGORIES[cat]["name_en"],
                "emoji": CATEGORIES[cat]["emoji"],
                "count": len(grouped.get(cat, [])),
                "items": [_clean_item(x) for x in grouped.get(cat, [])],
            }
            for cat in CATEGORIES
        },
        "all_items": [_clean_item(x) for x in sorted_items],
    }

    json_path = os.path.join(output_dir, f"ai-pulse-{date_str}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return md_path, json_path
