from datetime import datetime, timedelta, timezone
from typing import Dict, List


def get_test_items() -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    templates = [
        (
            "OpenAI releases GPT-5 reasoning model with new benchmark SOTA results",
            "OpenAI Blog",
            "Technical breakthrough paper shows major inference and architecture gains.",
            650,
            0,
        ),
        (
            "Anthropic unveils Claude API update with faster tool use beta",
            "Anthropic Blog",
            "Product launch brings new API release, enterprise preview and safety upgrades.",
            420,
            0,
        ),
        (
            "DeepSeek publishes open source weights and training recipe for 200B MoE model",
            "GitHub Trending",
            "Open source repository and community framework accelerate reproducible research.",
            0,
            1800,
        ),
        (
            "AI startup raises $100M seed to build vertical agent platform",
            "TechCrunch AI",
            "Funding round: startup founded by ex-Meta team raised $100M seed.",
            300,
            900,
        ),
        (
            "Safe Superintelligence secures $1.4B Series F at multi-billion valuation",
            "Crunchbase News",
            "Funding and venture dynamics reshape AI competition and market trend.",
            280,
            400,
        ),
        (
            "Robotics startup closes $2B Series C to scale humanoid manufacturing",
            "VentureBeat AI",
            "Massive funding round could shift industry roadmap for embodied AI.",
            260,
            700,
        ),
        (
            "YC launches new AI startup accelerator track for agent-native founders",
            "Y Combinator Blog",
            "Accelerator and founder ecosystem expansion highlights startup momentum.",
            190,
            520,
        ),
        (
            "Stealth AI startup exits stealth and launches compliance copilot for banks",
            "TechCrunch AI",
            "Startup launch targets regulated industry with policy-aware assistants.",
            220,
            600,
        ),
        (
            "Microsoft announces Copilot X update with multimodal API and code actions",
            "The Verge AI",
            "Launch and release update includes preview for enterprise users.",
            210,
            450,
        ),
        (
            "Google ships Gemini Studio beta with improved RAG and fine-tuning workflows",
            "Google AI Blog",
            "Product release adds developer tooling and inference optimization.",
            230,
            510,
        ),
        (
            "EU AI Act enforcement timeline accelerates as regulators publish guidance",
            "Ars Technica",
            "Regulation policy and ethics implications impact market competition.",
            170,
            300,
        ),
        (
            "China unveils national AI infrastructure plan focused on safety and compute",
            "\u673a\u5668\u4e4b\u5fc3",
            "Industry trend around policy, market incentives, and competition.",
            160,
            280,
        ),
        (
            "NVIDIA quarterly earnings beat expectations on AI datacenter demand",
            "Wired AI",
            "Market trend signals sustained investment in training and inference hardware.",
            200,
            360,
        ),
        (
            "vLLM hits major milestone with 10x community contributors and new release",
            "GitHub Trending",
            "Open source library update strengthens ecosystem and framework adoption.",
            180,
            2400,
        ),
        (
            "Hugging Face launches SmolLM3 open source model family",
            "Hugging Face Blog",
            "Open source launch introduces compact weights and benchmark improvements.",
            240,
            1300,
        ),
        (
            "Meta AI publishes paper on efficient long-context transformer architecture",
            "Meta AI Blog",
            "Research paper claims breakthrough for memory-efficient training.",
            260,
            500,
        ),
        (
            "Anthropic invests in safety startup focused on red-teaming frontier models",
            "Crunchbase News",
            "Investment and startup collaboration highlights policy and safety trend.",
            190,
            220,
        ),
        (
            "Open-source agent framework announces v2 release and plugin ecosystem",
            "GitHub Trending",
            "Repository growth and community library roadmap signal ecosystem expansion.",
            210,
            800,
        ),
        (
            "Perplexity launches enterprise research mode with private knowledge RAG",
            "VentureBeat AI",
            "Product launch and API integration target practitioner workflows.",
            230,
            610,
        ),
        (
            "Mistral introduces multilingual benchmark gains in new foundation model",
            "Import AI (Jack Clark)",
            "Technical breakthrough and research benchmark performance highlight novelty.",
            185,
            520,
        ),
        (
            "Figure and OpenAI expand partnership for factory-scale robotics pilots",
            "TechCrunch AI",
            "Industry trend and startup deployment indicate commercialization progress.",
            210,
            430,
        ),
        (
            "a16z publishes AI startup landscape and venture trend outlook",
            "a16z Blog",
            "Funding, valuation, and market trend report covers early-stage AI.",
            170,
            320,
        ),
        (
            "Alibaba open-sources multimodal MoE model and tooling on GitHub",
            "\u91cf\u5b50\u4f4d",
            "Open source release with repository, framework and community support.",
            175,
            720,
        ),
        (
            "Databricks acquires AI data startup to strengthen model training stack",
            "Crunchbase News",
            "Acquisition deal deepens platform competition and investor relevance.",
            165,
            310,
        ),
    ]

    items: List[Dict[str, object]] = []
    for idx, (title, source, content, hn_score, reddit_score) in enumerate(templates):
        published_dt = now - timedelta(hours=(idx % 23))
        items.append(
            {
                "id": f"mock-{idx+1}",
                "title": title,
                "url": f"https://example.com/ai-news/{idx+1}",
                "source": source,
                "source_type": "mock",
                "content": content,
                "published": published_dt.isoformat(),
                "published_dt": published_dt,
                "hn_score": hn_score,
                "reddit_score": reddit_score,
            }
        )
    return items


if __name__ == "__main__":
    sample = get_test_items()
    print(f"Generated test items: {len(sample)}")
