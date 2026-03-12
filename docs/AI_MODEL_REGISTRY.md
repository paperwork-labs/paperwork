# AI Model Registry

**Owner**: AI Operations Lead (`agent-ops.mdc`)
**Last updated**: March 2026
**Authoritative routing strategy**: Venture Master Plan v1, Section 0E

This is a living document. The AI Ops Lead updates it monthly with actual usage data and whenever a model swap occurs.

## Quality-First Routing Philosophy

Use the **best model for the task**. Only downgrade when a cheaper model produces **equivalent quality** -- not "good enough," equivalent. The founder is willing to pay more for better results. Cost optimization happens by routing to the right tier, not by forcing cheaper models where quality suffers.

**GPT-5 readiness**: When GPT-5 releases, evaluate immediately. If it outperforms current assignments at comparable cost, swap without waiting for a scheduled review cycle. The AI Ops Lead should generate a swap recommendation within 48 hours of any major model release.

---

## Current Model Assignments

| # | Model | Input/1M | Output/1M | Context | Role | Assigned Workflows |
|---|---|---|---|---|---|---|
| 1 | GPT-4o-mini | $0.15 | $0.60 | 128K | The Intern | W-2 OCR field mapping, classification, summaries, bulk extraction |
| 2 | Gemini 2.5 Flash | $0.30 | $2.50 | 1M | The Workhorse | Default for non-specialized tasks. State data extraction, trinket content, support bot responses |
| 3 | o4-mini | $1.10 | $4.40 | 200K | The Math Brain | Tax calculations, financial verification, bracket logic, refund computation |
| 4 | Gemini 2.5 Pro | $1.25 | $10.00 | 1M | The Researcher | Deep analysis, long-context research, SEO content drafts, competitive intel |
| 5 | GPT-4o | $2.50 | $10.00 | 128K | The Creative Director | Brand voice, social scripts, marketing copy, content calendar |
| 6 | GPT-5.4 | $2.50 | $15.00 | 1M | The Autonomous Agent | Market discovery (trinkets), autonomous browsing, competitor analysis, form filling |
| 7 | Claude Sonnet 4.6 | $3.00 | $15.00 | 200K | The Senior Engineer | Code generation (79.6% SWE-bench), legal compliance review, templates, PRDs |
| 8 | Claude Opus 4.6 | $5.00 | $25.00 | 1M | The Principal Engineer | Escalation only. >32K output, extended autonomy, complex architecture |
| 9 | o3 | $10.00 | $40.00 | 200K | Nuclear Option | Complex multi-step reasoning. Dense visual analysis. Almost never needed. |

### Interactive Session Guidance (Cursor IDE)

The routing strategy above covers **automated workflows** (n8n, batch operations). For interactive human-AI sessions:

| Session Type | Recommended Model | Rationale |
|---|---|---|
| Strategy / architecture / deep reasoning | Claude Opus 4.6 | Quality delta matters for high-stakes decisions. Deeper reasoning chains, better edge case detection. |
| Complex multi-file refactors | Claude Opus 4.6 | 1M context window, 80.8% SWE-bench, handles large scope well. |
| Routine coding / component building | Claude Sonnet 4.6 | 79.6% SWE-bench (only 1.2% below Opus). 40% cheaper. |
| Quick fixes / single-file edits | Claude Sonnet 4.6 or fast model | Minimal quality difference for small scope tasks. |

Using Opus for strategy sessions is not overkill -- these sessions drive $100K+ decisions.

---

## Monthly Cost Tracking

| Month | GPT-4o-mini | Gemini Flash | o4-mini | Gemini Pro | GPT-4o | GPT-5.4 | Sonnet | Opus | o3 | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|
| Mar 2026 | -- | -- | -- | -- | -- | -- | -- | -- | -- | **Pre-revenue** |
| Apr 2026 | | | | | | | | | | |
| May 2026 | | | | | | | | | | |
| Jun 2026 | | | | | | | | | | |

*Fill in actual API costs from provider dashboards monthly.*

---

## Swap History

| Date | Old Model | New Model | Workflows Affected | Reason | Monthly Cost Impact |
|---|---|---|---|---|---|
| (no swaps yet) | | | | | |

---

## Model Evaluation Queue

| Model | Release Date | Status | Notes |
|---|---|---|---|
| (none pending) | | | |

When a new model releases, AI Ops Lead evaluates within 48 hours per the protocol in `agent-ops.mdc`.

---

## Provider Dashboard Links

- **OpenAI**: https://platform.openai.com/usage
- **Anthropic**: https://console.anthropic.com/settings/billing
- **Google Cloud**: https://console.cloud.google.com/billing

---

## Decision Tree (Quick Reference)

1. Can it be done deterministically (code/rules)? -> No AI needed ($0)
2. High-volume + simple (classification, extraction)? -> GPT-4o-mini
3. Math/financial reasoning? -> o4-mini
4. Brand voice / creative copy? -> GPT-4o
5. Autonomous web browsing? -> GPT-5.4
6. Code generation or legal compliance? -> Claude Sonnet 4.6
7. Default for everything else -> Gemini 2.5 Flash
8. Escalation only (>32K output, multi-hour) -> Claude Opus 4.6
9. Nuclear (complex multi-step reasoning) -> o3

---

## Key Constraints

- NEVER assign Claude models to brand voice/creative copy (GPT-4o superior for narrative pull)
- NEVER assign GPT models to compliance/legal review (Claude superior for instruction adherence)
- NEVER send SSNs or unmasked PII to ANY model
- ALWAYS prefer Gemini 2.5 Flash as default when no specialized capability needed
- n8n is the implementation layer for all automated model routing
