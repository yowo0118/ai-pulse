import argparse
import json
import os
import time
from datetime import datetime
from typing import List

from collector import collect_all
from config import OUTPUT_DIR, TIME_WINDOW_HOURS, add_rss_source, get_rss_feeds, list_rss_sources, remove_rss_source
from reporter import generate_reports
from scorer import score_items


def print_banner() -> None:
    print("=" * 72)
    print("   ___    ___      ____        __          ")
    print("  / _ |  / _ )    / __ \\__ __ / / ___ ___ ")
    print(" / __ | / _  |   / /_/ / // // / (_-</ -_)")
    print("/_/ |_|/____/   / .___/\\_,_//_/ /___/\\__/ ")
    print("                /_/   Daily AI Intelligence")
    print("=" * 72)


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def save_collect_snapshot(items: List[dict]) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"collected-{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2, default=str)
    return path


def handle_source_management(args: argparse.Namespace) -> bool:
    if args.list_sources:
        print_section("SOURCE MANAGEMENT: LIST")
        rows = list_rss_sources()
        print(f"Current RSS sources: {len(rows)}")
        for row in rows:
            print(f"- [{row['state']}] {row['name']}: {row['url']}")
        return True

    if args.add_source:
        name, url = args.add_source
        ok, msg = add_rss_source(name, url)
        print(msg)
        return True

    if args.remove_source:
        ok, msg = remove_rss_source(args.remove_source)
        print(msg)
        return True

    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Pulse - Daily AI Intelligence Briefing")
    parser.add_argument("--collect-only", action="store_true", help="Only collect data, skip scoring/reporting")
    parser.add_argument("--dry-run", action="store_true", help="Collect + score, skip report generation")
    parser.add_argument("--list-sources", action="store_true", help="List current RSS sources")
    parser.add_argument("--add-source", nargs=2, metavar=("NAME", "URL"), help="Add or update a custom RSS source")
    parser.add_argument("--remove-source", metavar="NAME", help="Remove an RSS source by name")
    args = parser.parse_args()

    if handle_source_management(args):
        return

    start_ts = time.time()
    print_banner()

    anthropic = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    provider = "Anthropic" if anthropic else ("OpenAI" if openai else "Keyword Fallback")
    print(f"Scoring Mode: {provider}")
    print(f"Configured RSS sources: {len(get_rss_feeds())}")

    print_section("STEP 1/3 - COLLECT")
    items = collect_all(time_window_hours=TIME_WINDOW_HOURS)
    print(f"Collected items after dedupe: {len(items)}")

    if args.collect_only:
        snapshot = save_collect_snapshot(items)
        elapsed = time.time() - start_ts
        print_section("DONE")
        print(f"Collect-only mode complete in {elapsed:.1f}s")
        print(f"Collected snapshot: {snapshot}")
        return

    print_section("STEP 2/3 - SCORE")
    scored = score_items(items, use_ai=(anthropic or openai))
    print(f"Items passed score threshold: {len(scored)}")

    if not scored and items:
        print("No items passed threshold. Applying fallback policy (lower threshold / top 20).")
        scored = score_items(items, use_ai=False, min_score=3)
        if not scored:
            scored = score_items(items, use_ai=False, min_score=0)[:20]
        print(f"Fallback selected items: {len(scored)}")

    if args.dry_run:
        elapsed = time.time() - start_ts
        print_section("DONE")
        print(f"Dry-run complete in {elapsed:.1f}s")
        for i, item in enumerate(scored[:10], start=1):
            print(f"{i:02d}. [{item.get('score', 0)}] {item.get('title', '')}")
        return

    print_section("STEP 3/3 - REPORT")
    md_path, json_path = generate_reports(scored, output_dir=OUTPUT_DIR)

    elapsed = time.time() - start_ts
    print_section("DONE")
    print(f"Pipeline complete in {elapsed:.1f}s")
    print(f"Markdown report: {md_path}")
    print(f"JSON report: {json_path}")


if __name__ == "__main__":
    main()
