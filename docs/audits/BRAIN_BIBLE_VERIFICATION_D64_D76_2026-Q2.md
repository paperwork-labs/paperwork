# Brain Bible verification — D64–D76 (T1.1)

**Date:** 2026-05-04  
**Worktree:** `docs/t1.1-bible-d64-d76-verify`  
**Sources (non-invented):** `docs/KNOWLEDGE.md` (§D64–D76 historical + **D93**), `docs/audits/BRAIN_BIBLE_GAP_AUDIT_2026-05-03.md` (Tier 1 T1.1–T1.13 + Waves 0–2 patch list), `docs/BRAIN_ARCHITECTURE.md`.

## Scope note — two meanings of “D64–D76”

| Source | Meaning |
|--------|---------|
| `KNOWLEDGE.md` **### D64–D76** (dated 2026-03-13 … 2026-03-16) | Venture / product decisions (tax reconciliation, marketplace, Distill, filing engine, Workspace, etc.). |
| Gap audit + **D93** + bible | **Company OS / Studio** decisions reusing the **same id range** D64–D76 (2026-05-03 line in bible header). **D93** explicitly states the bible now carries this second set. |

Verification below checks **bible vs gap audit + D93**. Historical KNOWLEDGE rows D64–D76 are **not** expected to appear verbatim under those ids in the bible.

## Decision table

| Decision ID | Expected (from KNOWLEDGE + gap audit + D93) | Found in `BRAIN_ARCHITECTURE.md` | Severity | Proposed patch (one line) |
|-------------|---------------------------------------------|----------------------------------|----------|---------------------------|
| **D64** | **Gap audit T1.1:** Three operating modes (Consumer / Company OS / Meta-Product); `organization_id` framing; Mode 2 entities list; founder dogfood + Memory Moat to company; anti-pattern (third-party PM as source of truth for company ops). **Wave 0.1:** Also calls for top-level `## Operating Modes` *before* Reference Data Storage Doctrine. **D93:** “operating modes” among shipped D64–D76 topics. **KNOWLEDGE D64 (Mar):** Dual-path tax reconciliation — **not** claimed by D93/bible for this id. | [`### D64. Brain as Company OS`](../BRAIN_ARCHITECTURE.md#d64-brain-as-company-os--operating-modes-on-one-backend) (§1 Design Decisions): verbatim gap-audit block + summary bullets. **No** dedicated `## Operating Modes` section (gap audit Patch 0.1). | **P1** (structural) / else OK | Add `## Operating Modes` before `## Reference Data Storage Doctrine` and link/summarize D64 + D69 + D72 + D76 per gap audit Wave 0.1, **or** document intentional deferral in KNOWLEDGE. |
| **D65** | **T1.2:** Goal → Epic → Sprint → Task/PR → Decision; Conversation, TranscriptEpisode, AgentDispatch, Employee, Skill, Secret; Epic vs “workstream” naming; `/admin/workstreams` = Epics. **D93:** “internal ops schema.” **KNOWLEDGE D65 (Mar):** Financial marketplace stages — not bible intent for this id. | [`### D65`](../BRAIN_ARCHITECTURE.md#d65-internal-operations-schema--goal--epic--sprint--taskpr--decision) entity table + naming note; [`## 2A. Internal Operations Schema (Company OS)`](../BRAIN_ARCHITECTURE.md#2a-internal-operations-schema-company-os) with expanded hierarchy (gap audit Patch 0.2 intent). | OK | — |
| **D66** | **T1.3:** Conversations as primary founder action surface; shared schema with consumer chat; lifecycle (create, thread, state, react, persona-reply); canonical tag list; urgency SLA table; 30s iPhone PWA doctrine. **D93:** “conversations.” **KNOWLEDGE D66 (Mar):** Strategic architecture — not bible intent. | [`### D66`](../BRAIN_ARCHITECTURE.md#d66-conversations-as-the-founder-action-surface) with verbatim gap-audit block; §8 nav cites Conversations. | OK | — |
| **D67** | **T1.4:** TranscriptEpisode; ingest paths; sprint markdown ingest (planned); separation from D66. **D93:** “transcripts.” **KNOWLEDGE D67 (Mar):** Business tax 1065/1120-S — not bible intent. | [`### D67`](../BRAIN_ARCHITECTURE.md#d67-transcripts-as-knowledge) + verbatim block; write/read path expectations stated. | OK | — |
| **D68** | **T1.5:** AgentDispatch first-class; fields/outcomes/preflight; JSON→DB transitional; mapping table CP3; weekly-audit-digest. **D93:** “agent dispatch.” **KNOWLEDGE D68 (Mar):** Growth channels — not bible intent. | [`### D68`](../BRAIN_ARCHITECTURE.md#d68-agent-dispatch-as-a-first-class-entity) + CP3-style file→table mapping table. | OK | — |
| **D69** | **T1.6:** Five ship criteria; failure modes; auto-close + `verification_completed_at` proposal; `shipped_unverified` / `verification-debt`; **cross-ref** `production-verification.mdc` + `no-silent-fallback.mdc` as enforcement layers per audit §Tier 6 narrative. **D93:** “verification.” **KNOWLEDGE D69 (Mar):** Distill B2B — not bible intent. | [`### D69`](../BRAIN_ARCHITECTURE.md#d69-end-to-end-verification-at-the-workstream-layer-phone--desktop): five criteria + failure modes + auto-close + no-silent-fallback **paragraph**; cites `production-verification.mdc` in intro and verbatim item 1. | **P3** | Add explicit “data-layer: `.cursor/rules/no-silent-fallback.mdc`” cross-reference beside production-verification in the D69 intro sentence. |
| **D70** | **T1.7:** Studio as canonical Company OS surface; five criteria + anti-patterns; Tier 5 matrix. **D93:** Studio §8 + matrix. **KNOWLEDGE D70 (Mar):** Package split — not bible intent. | [`### D70 Studio Admin Surface Coverage Matrix`](../BRAIN_ARCHITECTURE.md#d70-studio-admin-surface-coverage-matrix) → [`## 8. Studio Dashboard`](../BRAIN_ARCHITECTURE.md#8-studio-dashboard-admin--company-os-surface) + **Studio admin coverage matrix (Tier 5)** table; `admin-navigation.tsx` contract. | OK | — |
| **D71** | **T1.8:** Five ingest categories (plans, sprints, KNOWLEDGE D##, `.mdc` rules, bible); `/admin/health` freshness + `alert` if >24h stale. **D93:** “reference pipeline.” **KNOWLEDGE D71 (Mar):** Distill brand — not bible intent. | [`### D71`](../BRAIN_ARCHITECTURE.md#d71-reference-knowledge-pipeline): summary line lists all five; verbatim block includes rules table + `bible_doc`. | OK | — |
| **D72** | **T1.9:** Sankalp + Olga only canary; 24h; Olga onboarding; procedural memory / weekly-audit-digest signal. **D93:** “dogfood.” **KNOWLEDGE D72 (Mar):** State Filing Engine 3-tier — not bible intent. | [`### D72`](../BRAIN_ARCHITECTURE.md#d72-founder-dogfood-mode-company-os) + verbatim block. | OK | — |
| **D73** | **T1.10:** Inverse of reference data doctrine; `apis/brain/data/*` transitional; migration rule (a)/(b); dead-file strike; `/admin/health` + `alert` on stale/missing JSON ref. **D93:** “JSON→DB migration.” **KNOWLEDGE D73 (Mar):** Paperwork Labs naming — not bible intent. | [`### D73`](../BRAIN_ARCHITECTURE.md#d73-json-file-to-brain-db-migration-doctrine) + verbatim block. | OK | — |
| **D74** | **T1.11 / Wave 2.6:** P0–P10 vs Waves vs epic/workstream ids; single-table reconciliation; rule: canonical **Epic** `epic-ws-{NN}-{kebab}`. **KNOWLEDGE D74 (Mar):** Distill acceleration — not bible intent. | [`### D74`](../BRAIN_ARCHITECTURE.md#d74-phase--wave--epic-naming-reconciliation) + pointer to [`## 20A. Phase ↔ Wave ↔ Epic ↔ Workstream reconciliation`](../BRAIN_ARCHITECTURE.md#20a-phase--wave--epic--workstream-reconciliation). | OK | — |
| **D75** | **T1.12 / Wave 2.1:** Three-token taxonomy + CORS; amend D9. **KNOWLEDGE D75 (Mar):** Agent-driven ops + n8n — not bible intent. | [`### D75`](../BRAIN_ARCHITECTURE.md#d75-brain--studio-internal-api-contract--token-taxonomy-cors-admin-auth); [`### D9`](../BRAIN_ARCHITECTURE.md#d9-internal-authentication) links to D75 per **D93**. | OK | — |
| **D76** | **T1.13 / Wave 0.1 sibling:** Schema + model + GET routes + Studio page same PR; founder checklist; anti-orphan; CI rg guard mentioned in audit skeleton. **D93:** “schema/surface co-ship.” **KNOWLEDGE D76 (Mar):** Google Workspace seat — not bible intent. | [`### D76`](../BRAIN_ARCHITECTURE.md#d76-schema-to-surface-co-shipping) + verbatim four-item block + PR-template line. | OK | — |

## Rollup

- **P0 MISSING:** none — substantive doctrine for gap-audit **T1.1–T1.13** is present under **`### D64`–`### D76`** in §1, with **§2A**, **§8** (incl. Tier 5 matrix), and **§20A** as cited anchors.
- **P1:** Gap audit **Wave 0.1** top-level **`## Operating Modes`** section (before Reference Data) was **not** implemented; content is consolidated under §1 headers instead.

## OPEN QUESTIONS

1. **ID collision in `KNOWLEDGE.md`:** Historical **D64–D76** (March) remain in the decision log with different meanings than bible **D64–D76** (May). **D93** explains the bible extension but does not rename the March rows. Should a future doc PR introduce aliases (e.g. “pre–Company-OS D64”) or move March content to new ids?
2. **`## Operating Modes`:** Is omission of a dedicated top-level section (**gap audit Patch 0.1**) intentional consolidation, or should the bible be patched to match the audit’s navigation structure?

## Method

1. Read **D93** and historical **D64–D76** in `docs/KNOWLEDGE.md`.  
2. Read **T1.1–T1.13** and **Waves 0–2** in `docs/audits/BRAIN_BIBLE_GAP_AUDIT_2026-05-03.md`.  
3. `rg` + read `docs/BRAIN_ARCHITECTURE.md` for each decision id and §8 / §20A / §2A.

---

*Verification artifact for Track 1, T1.1.*
