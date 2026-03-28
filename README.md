# zer0lint

**AI memory extraction diagnostics.** Most mem0 users are storing 0% of signal without knowing it — zer0lint finds the gap and fixes it in one command.

[![PyPI version](https://img.shields.io/pypi/v/zer0lint)](https://pypi.org/project/zer0lint/)
[![Python 3.9+](https://img.shields.io/pypi/pyversions/zer0lint)](https://pypi.org/project/zer0lint/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Made by Hermes Labs](https://img.shields.io/badge/made%20by-Hermes%20Labs-purple)](https://hermes-labs.ai)

---

## The Problem

You set up mem0 and your AI agent still seems forgetful. Technical decisions, version numbers, experiment results — it stores them, but can't recall them.

**The failure is silent.** `add()` returns success. `search()` returns results. Benchmarks look fine. But when the extraction step produces malformed JSON or drops specifics, the facts never land. You won't see an error. You'll just notice your agent doesn't remember.

**Proof from a real run (2026-03-22, mistral:7b, default mem0 config):**

```
Score  : 0/5 (0%) — CRITICAL
  ⚠  Model upgrade: We switched from gpt-3.5-turbo to gpt-4o-mini...
  ⚠  API endpoint: The API service runs on port 8421 with TLS 1.3...
  ⚠  CI status: CI pipeline passed on 2026-03-22 at commit a3f8c12...
  ⚠  Configuration: Auth tokens expire after 3600 seconds...
  ⚠  Version update: Updated Redis cluster to v7.2.4...
```

**After running `zer0lint generate` (same model, same config, new extraction prompt):**

```
Score  : 5/5 (100%) — HEALTHY
  Δ    : +100pp
```

That is a 0%→100% jump. Same model. One config change.

---

## Quick Start

```bash
pip install zer0lint

# Check your current extraction health
zer0lint check --config ~/.cogito/config.json

# Diagnose and fix
zer0lint generate --config ~/.cogito/config.json

# Dry run (see what would change without applying)
zer0lint generate --config ~/.cogito/config.json --dry-run
```

---

## What It Does

### `zer0lint check`
Tests your current mem0 config against domain-relevant synthetic facts. Returns a score and status.

```
zer0lint v0.1.0 — extraction health check
Config : ~/.cogito/config.json
Model  : mistral:7b
Prompt : default (mem0 built-in)

Error in new_retrieved_facts: Unterminated string starting at: line 1 column 10 (char 9)
Error in new_retrieved_facts: Expecting ',' delimiter: line 1 column 13 (char 12)

[CHECK] Using model: mistral:7b
[CHECK] Testing with 5 synthetic facts...
[CHECK] Score: 0/5 (0%) — CRITICAL
  ⚠  Model upgrade: We switched from gpt-3.5-turbo to gpt-4o-mini...
  ⚠  API endpoint: The API service runs on port 8421 with TLS 1.3...
  ⚠  CI status: CI pipeline passed on 2026-03-22 at commit a3f8c12...
  ⚠  Configuration: Auth tokens expire after 3600 seconds...
  ⚠  Version update: Updated Redis cluster to v7.2.4...

Score  : 0/5 (0%) — CRITICAL
Run zer0lint generate to diagnose and fix.
```

Statuses: **HEALTHY** (≥80%) · **ACCEPTABLE** (60–79%) · **DEGRADED** (40–59%) · **CRITICAL** (<40%)

### `zer0lint generate`
3-phase diagnostic + fix:

1. **Baseline** — test your config as-is
2. **Re-test** — inject zer0lint's domain-aware extraction prompt at config level
3. **Apply** — if improved, write the validated prompt to your config

```
[1/3] Baseline — testing current config as-is...
  Baseline score: 0/5 (0%)
    ❌ Configuration
    ❌ API endpoint
    ❌ CI status
    ❌ Model upgrade
    ❌ Version update

[2/3] Re-testing with zer0lint technical extraction prompt (config-level)...
  Improved score: 5/5 (100%)
  Improvement: +100pp
    ✅ Configuration
    ✅ API endpoint
    ✅ CI status
    ✅ Model upgrade
    ✅ Version update

Results:
  Before : 0/5 (0%)
  After  : 5/5 (100%)
  Δ      : +100pp
✅ Fix applied to config.
```

---

## Why Config-Level Injection Matters

**Important finding:** In mem0 v1.x, passing a prompt via `memory.add(..., prompt=X)` has **no measurable effect** on retrieval quality. The extraction prompt must live in the config (`custom_fact_extraction_prompt` field) to actually work.

zer0lint writes the validated prompt directly to your config — this is the correct fix.

---

## Supported Systems

| System | Status | Notes |
|---|---|---|
| mem0 (v1.x) | ✅ Supported | Full check + generate |
| Zep / Graphiti | 🔜 Planned | v0.3 |
| LangMem | 🔜 Planned | v0.4 |
| Generic adapter | 🔜 Planned | BYOC callables |

---

## Test Results (2026-03-22)

Horse race across models (5 technical + research facts):

| Model | Default prompt | zer0lint prompt | Δ |
|---|---|---|---|
| qwen3.5:4b | 80% | **100%** | +20pp |
| mistral:7b | **0%** | **100%** | **+100pp** |

**mistral:7b with the default mem0 prompt** produces malformed JSON, silently dropping all facts (0% recall). zer0lint's technical extraction prompt fixes this completely — 0%→100% on the same model with no other changes.

Scale test (10 facts, 5 domains):

| | Score | % |
|---|---|---|
| Default | 7/10 | 70% |
| zer0lint | 9/10 | **90%** |

---

## Ecosystem

zer0lint is the ingestion health layer. Pair it with:

**[cogito-ergo](https://github.com/roli-lpci/cogito-ergo)** — Production-ready two-stage memory retrieval. cogito-ergo uses zer0lint's technical extraction prompt by default. Recommended pipeline: run `zer0lint generate` first to validate ingestion, then deploy cogito-ergo for retrieval. No point optimizing retrieval if extraction is broken.

**[zer0dex](https://github.com/roli-lpci/zer0dex)** — Dual-layer memory architecture (compressed index + vector store). zer0lint ensures the facts being indexed are actually extracted correctly before they enter the dual-layer store.

**Recommended pipeline:**
```
zer0lint check     # is extraction working?
zer0lint generate  # fix it if not
cogito-ergo        # now deploy retrieval on clean data
```

---

## Installation

```bash
# From PyPI (recommended)
pip install zer0lint

# From source
git clone https://github.com/roli-lpci/zer0lint
cd zer0lint
pip install -e .
```

**Requirements:** Python 3.9+, mem0 v1.x, an Ollama or cloud LLM configured in your mem0 config.

---

## How It Works

zer0lint reads your existing mem0 config, borrows whatever LLM you already have configured, and runs a controlled recall test. No new API keys, no new models, no cloud calls beyond what you already have.

The extraction prompt it generates is **domain-aware** — tuned for technical/research work rather than personal assistant use cases. It's validated against synthetic facts before being applied, and your original config is always backed up.

---

## Built by Hermes Labs

zer0lint is part of the [Hermes Labs](https://hermes-labs.ai) AI agent tooling suite:

- **[lintlang](https://github.com/roli-lpci/lintlang)** — Static linter for AI agent tool descriptions and prompts
- **[Little Canary](https://github.com/roli-lpci/little-canary)** — Prompt injection detection
- **[Suy Sideguy](https://github.com/roli-lpci/suy-sideguy)** — Runtime policy enforcement for agents
- **zer0lint** — Memory extraction diagnostics ← you are here

---

## License

Apache 2.0
