# Paperwork Labs — AI Model Registry

**Owner**: AI Operations Lead (`agent-ops.mdc`)
**Last updated**: 2026-03-18
**Authoritative routing strategy**: Paperwork Labs Venture Master Plan v1, Section 0E

This is a living document. The AI Ops Lead updates it monthly with actual usage data and whenever a model swap occurs.

## Quality-First Routing Philosophy

Use the **best model for the task**. Only downgrade when a cheaper model produces **equivalent quality** -- not "good enough," equivalent. The founder is willing to pay more for better results. Cost optimization happens by routing to the right tier, not by forcing cheaper models where quality suffers.

---

## Model Roster

| # | Model | Input/1M | Output/1M | Context | Role |
|---|---|---|---|---|---|
| 1 | GPT-4o-mini | $0.15 | $0.60 | 128K | The Intern — bulk extraction, classification, summaries |
| 2 | Gemini 2.5 Flash | $0.30 | $2.50 | 1M | The Workhorse — default for non-specialized tasks |
| 3 | o4-mini | $1.10 | $4.40 | 200K | The Math Brain — tax/financial reasoning |
| 4 | Gemini 2.5 Pro | $1.25 | $10.00 | 1M | The Researcher — deep analysis, long-context |
| 5 | GPT-4o | $2.50 | $10.00 | 128K | The Creative Director — brand voice, marketing copy |
| 6 | GPT-5.4 | $2.50 | $15.00 | 1M | The Autonomous Agent — browsing, market discovery |
| 7 | Claude Sonnet 4.6 | $3.00 | $15.00 | 200K | The Senior Engineer — code gen, legal compliance |
| 8 | Claude Opus 4.6 | $5.00 | $25.00 | 1M | The Principal Engineer — escalation only |
| 9 | o3 | $10.00 | $40.00 | 200K | Nuclear Option — complex multi-step reasoning |

---

## Deployed Model Assignments (What's Actually Running)

These are the models currently deployed in production n8n workflows and API endpoints. Updated when models are swapped.

### n8n Workflows

| Workflow | Model | Expected Role | Deviation? | Env Var |
|---|---|---|---|---|
| agent-thread-handler | gpt-4o-mini | Intern | No | THREAD_HANDLER_MODEL |
| ea-daily | gpt-4o-mini | Intern | No | EA_DAILY_MODEL |
| ea-weekly | gpt-4o-mini | Intern | No | EA_WEEKLY_MODEL |
| sprint-kickoff | gpt-4o | Creative Director | No | SPRINT_KICKOFF_MODEL |
| sprint-close | gpt-4o | Creative Director | No | SPRINT_CLOSE_MODEL |
| pr-summary | gpt-4o-mini | Intern | No | PR_SUMMARY_MODEL |
| social-content-generator | gpt-4o | Creative Director | No — fixed 2026-03-18 (was gpt-4o-mini) | SOCIAL_CONTENT_MODEL |
| growth-content-writer | gpt-4o | Creative Director | No — fixed 2026-03-18 (was gpt-4o-mini) | GROWTH_CONTENT_MODEL |
| partnership-outreach-drafter | gpt-4o | Creative Director | No | PARTNERSHIP_MODEL |
| cpa-tax-review | gpt-4o | Creative Director | Yes — should be Claude Sonnet (compliance) | CPA_REVIEW_MODEL |
| qa-security-scan | gpt-4o | Creative Director | Yes — should be Claude Sonnet (code/security) | QA_SCAN_MODEL |
| weekly-strategy-checkin | gpt-4o | Creative Director | No | STRATEGY_MODEL |
| decision-logger | (no AI node) | N/A | N/A | N/A |

### API Endpoints

| Endpoint | Model | Expected Role | Deviation? |
|---|---|---|---|
| FileFree advisory (`/api/advisory`) | gpt-4o (env: ADVISORY_MODEL) | Creative Director | No — fixed 2026-03-18 (was gpt-4o-mini) |
| FileFree OCR extraction | gpt-4o-mini | Intern | No |
| FileFree OCR fallback | gpt-4o (vision) | Creative Director | No — quality fallback for low-confidence |

### Cursor IDE Sessions

| Session Type | Recommended Model | Rationale |
|---|---|---|
| Strategy / architecture / deep reasoning | Claude Opus 4.6 | Quality delta matters for high-stakes decisions |
| Complex multi-file refactors | Claude Opus 4.6 | 1M context, 80.8% SWE-bench |
| Routine coding / component building | Claude Sonnet 4.6 | 79.6% SWE-bench, 40% cheaper |
| Quick fixes / single-file edits | Fast model | Minimal quality difference |

---

## Activation Roadmap (Planned But Not Yet Deployed)

| Model | Target Use | Blocked By | ETA |
|---|---|---|---|
| Claude Sonnet 4.6 | CPA Tax Review, QA Security Scan | Anthropic API key not configured in n8n | When Anthropic account is set up |
| o4-mini | Tax calculation verification | Tax engine not yet built | Phase 2 |
| Gemini 2.5 Flash | State data extraction (LaunchFree) | LaunchFree not yet in development | Phase 3 |
| GPT-5.4 | Trinket market discovery | Trinkets pipeline not yet built | Phase 1.5 |
| Gemini 2.5 Pro | Competitive intel, SEO drafts | No current workflow needs it | Phase 5 |

---

## Decision Tree (Quick Reference)

1. Can it be done deterministically (code/rules)? → No AI needed ($0)
2. High-volume + simple (classification, extraction)? → GPT-4o-mini
3. Math/financial reasoning? → o4-mini
4. Brand voice / creative copy? → GPT-4o
5. Autonomous web browsing? → GPT-5.4
6. Code generation or legal compliance? → Claude Sonnet 4.6
7. Default for everything else → Gemini 2.5 Flash
8. Escalation only (>32K output, multi-hour) → Claude Opus 4.6
9. Nuclear (complex multi-step reasoning) → o3

---

## Monthly Cost Tracking

| Month | GPT-4o-mini | Gemini Flash | o4-mini | Gemini Pro | GPT-4o | GPT-5.4 | Sonnet | Opus | o3 | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|
| Mar 2026 | -- | -- | -- | -- | -- | -- | -- | -- | -- | **Pre-revenue** |
| Apr 2026 | | | | | | | | | | |

*Fill in actual API costs from provider dashboards monthly.*

---

## Swap History

| Date | Old Model | New Model | Workflows Affected | Reason | Monthly Cost Impact |
|---|---|---|---|---|---|
| 2026-03-18 | gpt-4o-mini | gpt-4o | social-content-generator, growth-content-writer | Brand voice requires higher quality model | ~+$0.50/run |
| 2026-03-18 | gpt-4o-mini | gpt-4o | FileFree advisory route.ts | User-facing advisory quality | ~+$0.02/request |
| 2026-03-18 | gpt-4o | gpt-4o-mini | ea-daily, ea-weekly | Briefings don't need full gpt-4o; token limit fix | ~-$0.10/run |

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

## Key Constraints

- NEVER assign Claude models to brand voice/creative copy (GPT-4o superior for narrative pull)
- NEVER assign GPT models to compliance/legal review (Claude superior for instruction adherence)
- NEVER send SSNs or unmasked PII to ANY model
- ALWAYS prefer Gemini 2.5 Flash as default when no specialized capability needed
- n8n is the implementation layer for all automated model routing
- See `agent-ops.mdc` for New Workflow Checklist and Model Swap Protocol
