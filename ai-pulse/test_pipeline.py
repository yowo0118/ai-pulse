import argparse
from typing import Set

from config import CATEGORIES, OUTPUT_DIR
from reporter import generate_reports
from scorer import score_items
from test_data import get_test_items


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Pulse pipeline verification with mock data")
    parser.add_argument("--ai", action="store_true", help="Enable real API scoring if keys are available")
    args = parser.parse_args()

    print("[Test] Loading mock data...")
    items = get_test_items()
    print(f"[Test] Mock items: {len(items)}")

    print("[Test] Scoring items...")
    scored = score_items(items, use_ai=args.ai)
    print(f"[Test] Scored items (>=5): {len(scored)}")

    categories: Set[str] = {str(x.get("category", "")) for x in scored}
    expected = set(CATEGORIES.keys())
    high_count = sum(1 for x in scored if x.get("importance") == "high")
    scores = [float(x.get("score", 0)) for x in scored]
    score_min = min(scores) if scores else 0.0
    score_max = max(scores) if scores else 0.0

    md_path, json_path = generate_reports(scored, output_dir=OUTPUT_DIR)
    print(f"[Test] Markdown report: {md_path}")
    print(f"[Test] JSON report: {json_path}")

    print("\n[Test] Validation")
    print(f"- Categories covered: {len(categories)} / {len(expected)}")
    print(f"- Covered categories: {sorted(categories)}")
    print(f"- Missing categories: {sorted(expected - categories)}")
    print(f"- High importance count: {high_count}")
    print(f"- Score range: {score_min:.1f} - {score_max:.1f}")

    with open(md_path, "r", encoding="utf-8") as f:
        preview = f.read(3000)
    print("\n[Test] Markdown preview (first 3000 chars):")
    print(preview)

    checks_ok = True
    if not expected.issubset(categories):
        print("[FAIL] Not all 6 categories are covered.")
        checks_ok = False
    if high_count <= 0:
        print("[FAIL] High importance count should be > 0.")
        checks_ok = False
    if score_min < 5 or score_max > 10:
        print("[FAIL] Score range should stay within 5-10 after filtering.")
        checks_ok = False

    if checks_ok:
        print("\n[PASS] Pipeline validation passed.")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
