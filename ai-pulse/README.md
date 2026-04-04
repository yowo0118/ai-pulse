# AI Pulse

AI Pulse is a Python backend system that collects AI industry news from 30+ sources, scores each item with AI (or keyword fallback), generates ChatGPT summaries for every item, and outputs bilingual daily briefings in Markdown and JSON.

## Quick Start

1. Enter the project directory.

```bash
cd ai-pulse
```

2. Run the local verification pipeline with mock data.

```bash
python test_pipeline.py
```

3. Run the real pipeline.

```bash
python main.py
```

## Output Files

- `output/ai-pulse-YYYY-MM-DD.md`
- `output/ai-pulse-YYYY-MM-DD.json`

If `FEISHU_BOT_WEBHOOK` is configured, AI Pulse also sends the generated report to your Feishu bot automatically.

## CLI Usage

```bash
# collect only
python main.py --collect-only

# collect + score only
python main.py --dry-run

# list current RSS sources
python main.py --list-sources

# add or override a source
python main.py --add-source "My Feed" "https://example.com/feed.xml"

# remove a source
python main.py --remove-source "My Feed"
```

## Data Source Summary

| Source Type | Count | Notes |
|---|---:|---|
| RSS (Media/Labs/Substack/VC/CN) | 24+ | Core news + labs + funding + Chinese outlets |
| Hacker News | Top 200/day | Keyword + score filtered |
| Reddit | 5 subreddits | Hot posts with score threshold |
| GitHub Trending | 4 topics | Regex repo extraction + dedupe |

## Architecture

```text
                +------------------+
                |    config.py     |
                | feeds/categories |
                +---------+--------+
                          |
                          v
 +-----------+    +-------+--------+    +-----------+
 | collector  +---> collect_all()   +---> scorer.py |
 | RSS/HN/... |    +-------+--------+    | AI/keyword|
 +-----------+            |             +-----+-----+
                          |                   |
                          v                   v
                     deduplicate         scored items
                          \                   /
                           \                 /
                            v               v
                           +-------------------+
                           |    reporter.py    |
                           | markdown + json   |
                           +---------+---------+
                                     |
                                     v
                                  output/
```

## GitHub Actions

Workflow file: `.github/workflows/daily.yml`

- Trigger: daily at `00:00 UTC` + manual dispatch
- Runtime: Ubuntu + Python 3.11
- Command: `python main.py`
- Commit: auto-commit `output/` updates

Set secret:

- `ANTHROPIC_API_KEY` (optional; if not set, keyword fallback is used)
- `OPENAI_API_KEY` (recommended for per-article ChatGPT summaries)
- `FEISHU_BOT_WEBHOOK` (optional; for auto delivery to Feishu)

## Cron Example

```bash
0 8 * * * cd /path/to/ai-pulse && /usr/bin/python3 main.py
```

## Customization

- Update source lists and categories in `config.py`
- Tune thresholds: `MIN_SCORE`, `MAX_PER_CATEGORY`, `TIME_WINDOW_HOURS`
- Use Anthropic by setting `ANTHROPIC_API_KEY`
- Use OpenAI by setting `OPENAI_API_KEY` (optional `OPENAI_MODEL`)
- Set `OPENAI_SUMMARY_MODEL` to control the summary model (default follows `OPENAI_MODEL`, fallback `gpt-4.1-mini`)
- Set `FEISHU_BOT_WEBHOOK` to push report text to your Feishu bot

## Notes

- Python 3.9+ standard library only
- All HTTP requests use `User-Agent` and `timeout=15`
- Single-source failures are isolated and do not crash the pipeline
