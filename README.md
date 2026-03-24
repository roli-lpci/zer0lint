# zer0lint

**AI memory extraction diagnostics.** Find out why your AI agent forgets what matters — and fix it.

[![PyPI version](https://img.shields.io/pypi/v/zer0lint)](https://pypi.org/project/zer0lint/)
[![Python 3.9+](https://img.shields.io/pypi/pyversions/zer0lint)](https://pypi.org/project/zer0lint/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Made by Hermes Labs](https://img.shields.io/badge/made%20by-Hermes%20Labs-purple)](https://hermes-labs.ai)

---

## The Problem

You set up mem0 (or Zep, or LangMem) and your AI agent still seems forgetful. Technical decisions, version numbers, experiment results — it stores them, but can't recall them.

**Why?** mem0's default extraction prompt is designed for personal assistants: favorite coffee shops, dietary preferences, weekend plans. When your agent stores "Redis upgraded to v7.2.4" or "security audit scored 7.2/10", it silently drops the specifics.

**Proven gap (our testing):**
- Default mem0 prompt → **70% recall** on technical facts
- Wrong domain prompt (personal) → **40% recall**
- zer0lint technical prompt → **90% recall**

That's a **+20pp improvement** from getting the extraction prompt right.

---

## Quick Start

```bash
pip install zer0lint

# Check your current extraction health
zer0lint check --config ~/.mem0/config.json

# Diagnose and fix
zer0lint generate --config ~/.mem0/config.json

# Dry run (see what would change without applying)
zer0lint generate --config ~/.mem0/config.json --dry-run
```

---

## What It Does

### `zer0lint check`
Tests your current mem0 config against domain-relevant synthetic facts. Returns a score and status.

```
zer0lint v0.2.0 — extraction health check
Config : ~/.mem0/config.json
Model  : qwen3.5:4b
Prompt : default (mem0 built-in)

Score  : 4/5 (80%) — HEALTHY

  ✅ Version update
  ✅ CI status
  ✅ Model upgrade
  ✅ Configuration
  ⚠  API endpoint
```

Statuses: **HEALTHY** (≥80%) · **ACCEPTABLE** (60–79%) · **DEGRADED** (40–59%) · **CRITICAL** (<40%)

### `zer0lint generate`
3-phase diagnostic + fix:

1. **Baseline** — test your config as-is
2. **Re-test** — inject zer0lint's domain-aware extraction prompt at config level
3. **Apply** — if improved, write the validated prompt to your config

```
zer0lint v0.2.0 — extraction optimizer

[1/3] Baseline — testing current config as-is...
  Baseline score: 4/5 (80%)

[2/3] Re-testing with zer0lint technical extraction prompt...
  Improved score: 5/5 (100%)
  Improvement: +20pp

Results:
  Before : 4/5 (80%)
  After  : 5/5 (100%)
  Δ      : +20pp

✅ Fix applied to config.
   Backup: ~/.mem0/config.backup.2026-03-23T14:20:00
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

## Test Results (2026-03-23)

Horse race across models (5 technical + research facts):

| Model | Default prompt | zer0lint prompt | Δ |
|---|---|---|---|
| qwen3.5:4b | 80% | **100%** | +20pp |
| mistral:7b | 40% | 40% | 0pp |

**mistral:7b** produces malformed JSON regardless of prompt — model quality is the bottleneck. zer0lint detects this and recommends switching models.

Scale test (10 facts, 5 domains):

| | Score | % |
|---|---|---|
| Default | 7/10 | 70% |
| zer0lint | 9/10 | **90%** | 

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
