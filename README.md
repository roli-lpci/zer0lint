# zer0lint

**mem0 extraction optimizer** — Inspect your system, generate the extraction prompt that works for you, test it, apply it.

mem0's default extraction prompt is built for personal preference tracking. For technical work, research, code decisions, or domain-specific agents, it silently drops facts you need to remember.

zer0lint looks at what's actually in your memory, identifies the patterns, and generates a custom extraction prompt tuned to your system.

## Quick Start

```bash
pip install zer0lint

# Generate an optimized prompt for your mem0 system
zer0lint generate --config ~/.mem0/config.json --verbose

# It will:
# 1. Sample your existing memories
# 2. Analyze what categories of info you store
# 3. Generate a domain-specific extraction prompt
# 4. Test it against synthetic facts
# 5. Apply it to your config (if score >= 4/5)
```

## The Problem We're Solving

You set up mem0 to store facts from your work. But it keeps dropping technical details, version numbers, test results, or domain-specific information — silently, with no warning.

**Why?** mem0's default extraction prompt is optimized for general-purpose memory. When you ask it to remember "port 8421 TLS config", it returns empty. When you ask it to remember "my favorite coffee shop", it works fine.

**What we discovered:** The fix isn't a preset prompt. The fix is analyzing YOUR actual memories and generating THE prompt that matches YOUR patterns.

We did this manually for our own system:
- Day 1: Installed mem0, got 0/5 extraction ❌
- Days 2-9: Tried different models, analyzed patterns, wrote a custom prompt
- Day 10: 5/5 extraction ✅

zer0lint does this process automatically. One command.

## How It Works

```
zer0lint generate
├─ 1. Sample 20-30 of your existing memories
├─ 2. Identify patterns: What info do you actually store?
├─ 3. Generate a prompt matching those patterns
├─ 4. Test against synthetic facts (score it)
├─ 5. Iterate if needed (up to 3 rounds)
└─ 6. Apply to config (if score >= 4/5)
```

The generated prompt is tailored to your system's actual data.

## Requirements

- Python 3.9+
- mem0ai (pip installed)
- A configured mem0 instance with existing memories (or willingness to bootstrap)
- An extraction LLM (Ollama local, OpenAI, Groq, etc. — whatever mem0 supports)

## Installation

```bash
pip install zer0lint
```

## Usage

### Generate an Optimized Prompt

```bash
zer0lint generate --config ~/.mem0/config.json --verbose
```

Options:
- `--config PATH` — Path to mem0 config.json (auto-detects ~/.mem0/config.json if not provided)
- `--verbose` / `-v` — Show detailed progress
- `--apply` / `--no-apply` — Apply the prompt to config (default: apply)

Output:
```
zer0lint v0.1.0 — mem0 extraction optimizer

Config: /Users/you/.mem0/config.json
Running optimization flow...

✓ Optimization successful

Extraction quality: 5/5

Generated prompt:
[shows the custom prompt]

✓ Prompt applied to config
  Backup saved: /Users/you/.mem0/config.json.backup.2026-03-23T00:30:45

Log:
  • Sampled 28 memories
  • Detected categories: ['technical', 'research']
  • Generated 5 test facts
  • Generated prompt via LLM analysis
  • Prompt tested: 5/5
  • Applied prompt to config
```

## What Gets Generated?

The generated extraction prompt includes:

1. **Domain-specific categories** — Identified from your actual memories
2. **Category descriptions** — What this system should remember
3. **Concrete examples** — Input → Output in JSON format
4. **Extraction instructions** — "Extract generously, be specific"

Example generated prompt (technical domain):

```
You are a Technical Memory Organizer for software infrastructure.

Extract ALL technically significant facts. Focus on:
1. API endpoints, ports, and service addresses
2. Version numbers, model names, package identifiers
3. Configuration values, environment variables
4. Code decisions, architectural choices
...

Examples:
Input: "The API server runs on port 8421 with TLS enabled."
Output: {"facts": ["API server runs on port 8421", "TLS enabled"]}

Return facts as JSON with key "facts" and a list of strings. Extract generously.
```

## Limitations (v0.1)

- Requires at least 10-20 existing memories to identify patterns reliably
- Works with mem0ai >= 0.1.0
- No batch/async mode yet
- Iteration limit: 3 rounds (hardcoded)
- Does not modify memory content, only the extraction prompt

## Next Steps (v0.2)

- `zer0lint check` — Standalone health check without generation
- `zer0lint compare` — Side-by-side before/after comparison
- Prompt history and rollback
- Custom category hints (user-provided domain info)
- Integration with mem0's web UI

## Contributing

Found a bug? Have ideas? Open an issue or PR at github.com/roli-lpci/zer0lint

## License

MIT

---

**Made by Hermes Labs** — AI research & safety tooling | hermes-labs.ai

Questions? → rolando@hermes-labs.ai
