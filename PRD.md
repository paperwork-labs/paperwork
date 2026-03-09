# filefree.tax — Product Requirements Document

**Version**: 6.0
**Last Updated**: 2026-03-09
**Status**: MVP Definition (Revenue Model Overhaul + Final Alignment)

---

## 1. Product Overview

### 1.1 Problem Statement

~166M individual tax returns are filed annually in the US. ~70% of filers have simple tax situations (W2 income, standard deduction), yet they pay $0–$170+ to TurboTax or spend hours at H&R Block for what should be a 5-minute process. The IRS killed its free Direct File program for 2026. TurboTax faces active lawsuits for selling user data and deceptive pricing. 67% of Gen Z are stressed about filing. 40% have cried over it. The system is broken, and the alternatives are disappearing.

But the bigger problem is upstream: **filing your first tax return is the first real interaction most young Americans have with the financial system, and the experience is so traumatic that it creates lasting anxiety about all financial decisions.** No one is building for this moment.

### 1.2 Solution

filefree.tax is a mobile-first web application that **starts** as free, AI-powered tax preparation — snap a W2, get your completed return in minutes. But the real product is what comes next: a year-round AI tax advisor that helps Gen Z make smarter financial decisions, starting from the trust earned during that first filing.

**Phase 1 (2026):** Free tax prep — W2 photo to completed 1040 PDF in under 5 minutes. Tiered OCR pipeline (GCP Cloud Vision + GPT). E-file via partner at cost while our own IRS transmitter is certified.
**Phase 2 (2027):** Free e-file via own IRS MeF transmitter (NORTH STAR) + AI tax advisor subscription + financial product marketplace.
**Phase 3 (2028):** Embedded tax engine (B2B API) for fintechs, payroll providers, and neobanks.

### 1.3 Target User (MVP)

- Age 18-30 (Gen Z, especially first-time and early-career filers)
- Single filer OR Married filing jointly
- W2 income only (1-3 W2s)
- Standard deduction (no itemizing)
- No dependents (MVP), add dependents in v1.1
- No investment income, rental income, or self-employment (MVP)
- US resident, single state

### 1.4 Why This User — The Data

- 67% of Gen Z report stress about filing taxes (vs 57% all Americans) — Stagwell 2026
- 62% of Gen Z say tax season is their #1 financial stressor — AOL/Yahoo Finance
- 52% fear making errors; only 33% feel confident filing correctly
- 45% say filing negatively impacts their mental health
- 55% consider filing taxes "one of the hardest parts of adulting"
- 44% have already used AI for tax help (vs 4% of Boomers) — Stagwell 2026
- 70% would consider using AI-based tax prep — Stagwell 2026
- 40% procrastinate until the last minute; 50%+ had unfiled returns 3 days after April 15
- 50% of Gen Z have faced IRS fees, penalties, or collections — LendEDU
- 80% of tax software users stick with the same program year after year — PCMag

That last stat is the business case: **whoever captures a 22-year-old owns their tax relationship for a decade.**

### 1.5 Success Metrics

**2026 (Validation):**

- Email waitlist: 500+ by April 15, 2,000+ by October 15
- Beta users (complete full flow): 500 by October 15
- Completion rate: > 60% of users who start filing complete it
- NPS: > 50
- Share rate (tax receipt card): > 15% of completers
- Testimonials collected: 50+

**2027 (Revenue):**

- Total filers: 50,000
- AI Advisory subscribers: 2,500 (5% conversion)
- Financial product referrals: 5,000 (10% of filers)
- ARR: $500K+

**2028 (Scale):**

- Total filers: 500,000
- ARR: $5M+
- B2B API partners: 5+

---

## 2. Competitive Strategy

### 2.1 Market Landscape

**Market size:** US consumer tax prep ~$8.2B. Intuit (TurboTax) = $4.9B revenue, 60% market share.

**Filing volume:** 165.8M returns in 2025. 154.9M e-filed (93.4%). ~16.5M extension filers (10%). Average refund in 2026: $2,290 (up 10.9%).

### 2.2 Competitive Landscape (Honest Assessment)


| Competitor     | Federal               | State    | W2 OCR           | Speed       | Revenue Model                    | Threat to FileFree                                                        |
| -------------- | --------------------- | -------- | ---------------- | ----------- | -------------------------------- | ------------------------------------------------------------------------- |
| TurboTax       | "Free" (upsells)      | $39.99+  | Yes              | 30+ min     | Upsells + data                   | LOW (trust collapse, can't simplify without killing revenue)              |
| H&R Block      | "Free" (upsells)      | $37+     | Yes              | 30+ min     | Upsells + pro services           | LOW (same structural problem)                                             |
| FreeTaxUSA     | Free (all complexity) | $15.99   | Yes (unreliable) | 20-40 min   | State filing fees                | MODERATE (free federal for ALL complexity, 3.2% market share, $35.7M rev) |
| Cash App Taxes | Free                  | Free     | No               | 15-30 min   | Cross-sell to Cash App ecosystem | HIGH (truly free, but requires Cash App account)                          |
| **april**      | Embedded              | Embedded | Yes              | 36 screens  | B2B API fees                     | **CRITICAL (see below)**                                                  |
| **FileFree**   | **Free**              | **Free** | **Yes (AI)**     | **2-5 min** | **Advisory + referrals**         | —                                                                         |


### 2.3 The april Threat (Most Important Competitor)

april raised $78M ($38M Series B in July 2025). They are the first new company in 15+ years to achieve national e-file coverage in all 50 states. They're embedded in Chime, Gusto, and 30+ fintech platforms. They show users only 36 screens for federal + state combined. 60+ NPS.

**Why april doesn't kill us:** april is B2B2C — they're an API that other companies embed. They don't have a consumer brand. They don't show up when someone Googles "file taxes free." We're B2C. Different distribution, different positioning. A user who opens the App Store or Google looking for "free tax filing" will never find april.

**What we can learn from april:** Their 36-screen flow proves "ask only what's needed" works. Their success validates the market. Their embedded model is our Phase 3 — we should build toward B2B API as a revenue diversification play.

**E-file note:** We're building our own IRS MeF transmitter (NORTH STAR). Column Tax is our interim e-file partner (October 2026) at cost-passthrough while we complete IRS certification. april remains competitive intelligence for our Phase 3 B2B API strategy.

### 2.4 Honest Moat Assessment

**What is NOT a moat (but IS a differentiator):**

- Emotional design / anxiety-focused UX — Any well-funded competitor can hire good designers. TurboTax launched "TurboTax Simple" in 2025. This buys 6-12 months, not permanent advantage.
- Speed — april already does 36 screens. Speed is compressible. But incumbents can't strip down without losing revenue from complex filers, so this holds against TurboTax/H&R Block specifically.
- "Privacy-first" claims — Any startup can say this. Proving it requires time and track record.

**What IS defensible:**

**Moat 1: First-Filer Lock-In (STRUCTURAL)**
80% annual retention means whoever captures a 22-year-old filing their first return owns that customer for ~10 years. With ~4M Americans turning 22 each year, the first-filer market is ~4M/year. If we capture 5% of first-time filers, that's 200K users/year with 80% retention — compounding to 670K active users by year 5 without any other acquisition. This is the core business model.

**Moat 2: Trust-to-Advisory Pipeline (RELATIONSHIP)**
Free filing earns trust. Trust enables financial advisory. Advisory creates ongoing relationship (monthly engagement) that is 10x stickier than annual filing. Once a user relies on FileFree for "should I open a Roth IRA?" and "how much should I put in my 401k?", they're not switching for a $5/year savings on filing.

**Moat 3: Network Effects via Social Proof (DISTRIBUTION)**
Tax filing is social — "who do you use?" is a common question. The viral tax receipt card, referral system, and TikTok/Instagram content create compounding distribution. If 15% of users share their card and 5% of viewers convert, each user generates 0.0075 new users. At 100K users, that's 750 organic acquisitions per cycle — growing exponentially.

**Moat 4: Data Compound Interest (LONG-TERM)**
Each year of filing data makes the AI advisor smarter: "You made $12K more than last year — here's how to adjust your W-4 withholding so you're not giving the IRS an interest-free loan." Multi-year data is something new competitors can never have for existing users.

**Moat 5: Proprietary OCR Intelligence Layer (COST STRUCTURE)**
The moat isn't the OCR engine itself — it's the post-processing intelligence layer on top. Our pipeline: GCP Cloud Vision for text extraction + local SSN isolation (regex, never sent to AI) + GPT-4o-mini structured field mapping + GPT-4o vision fallback for edge cases. Cost: $0.004/doc vs competitors' $0.30+ (GCP Document AI W-2 Parser) or $0.03+ (AWS Textract). This 75x cost advantage means we can offer truly free filing at any scale. The intelligence layer is OCR-engine-agnostic (can swap Cloud Vision for PaddleOCR or Textract without changing the GPT pipeline) and is the foundation for our Phase 3 B2B API.

### 2.5 Marketing Narrative

"67% of Gen Z are stressed about taxes. TurboTax got caught selling your data. The IRS killed free filing. We built what should have existed all along — file in 5 minutes, free forever, and an AI advisor that actually helps you keep more of your money."

---

## 3. User Flow (MVP)

### Screen 0: Try Without Signing Up (Growth Unlock)

- User can snap/upload a W2 photo WITHOUT creating an account
- Show the OCR extraction magic (fields filling in one by one)
- Gate: "Create a free account to save your return and finish filing"
- This reduces the trust barrier to zero and creates shareable "wow" moments
- Anonymous session data converts to user account on sign-up

### Screen 1: Landing / Login

- Hero: anxiety-focused copy, not feature-focused
- Primary CTA: "Snap Your W2 — See It In Action" (try-before-signup)
- Secondary CTA: "Sign In" for returning users
- Social proof: filing counter, testimonials, trust badges
- Comparison section: FileFree vs TurboTax vs FreeTaxUSA
- FAQ section targeting Gen Z concerns ("Is this really free?", "Is my data safe?", "What's the catch?")
- Dedicated /pricing page linked from nav: explicit free-forever guarantee for core filing
- Auth: Email + password, or Google OAuth
- Mobile-optimized, dark theme with gradient accents

### Screen 2: Document Capture — W2

- Full-screen camera interface with W2 bounding box overlay
- Guide text: "Position your W2 within the frame"
- Manual capture button (auto-capture is stretch goal)
- Immediate quality check: blur detection, lighting check
- If quality fails: "That's a bit blurry. Try again with more light."
- Upload from photo library as alternative
- Multiple W2 support ("Add another W2" after first)

### Screen 3: Document Capture — Driver's License

- Same camera interface, DL-shaped bounding box
- Skippable: "Enter your info manually instead" link
- Front of DL only (MVP)
- Extract: Full name, address, DOB

### Screen 4: Confirm Extracted Data

- Clean, editable form with extracted data
- Confidence indicators: green (>95%), yellow (80-95% — "please verify"), red (<80% — empty, user types in)
- Manual entry fallback: if OCR fails, same form layout with all fields empty and W2 box-number labels
- "Everything look right?" CTA at bottom

### Screen 5: Filing Details

- Filing status selector (Single, MFJ, MFS, HoH) — large tappable cards
- Standard deduction auto-selected (shows amount)
- Dependents: greyed out with "Coming Soon" badge
- Only what's legally required — minimal

### Screen 6: Your Return Summary (THE MONEY SCREEN)

- Animated refund reveal (count-up) or calm owed display
- Breakdown: Gross Income, Standard Deduction, Taxable Income, Federal Tax, Already Paid, Refund/Owed
- Charts: "Where Your Taxes Go" pie chart, "Your Refund vs Average" bar chart
- AI Insights: plain-English explanation + personalized tips
- Tax receipt viral card: shareable graphic with filing time, opt-in refund amount, FileFree branding
- CTAs: "Download Your Completed Return (PDF)", "Add State Filing — Free"

### Screen 7: Download & Next Steps (MVP — no e-file yet)

- Completed 1040 PDF download
- Step-by-step submission instructions (IRS Free File or mail)
- "E-file coming January 2027 — we'll notify you"
- **AI Advisor teaser:** "Want to keep more of your money next year? Get personalized tax-saving tips year-round." → email capture for AI advisory waitlist
- Upsell: "Protect yourself with Audit Shield — $29/year"

### Screen 8: Dashboard (Post-Filing)

- Filing status card with return summary
- Download return PDF
- "File State Return" CTA
- **AI Advisor card:** monthly tax tip, "Your tax-saving opportunities" (preview of premium)
- Referral card: "Know someone who needs to file? Share FileFree"

---

## 4. Technical Requirements

### 4.1 Document Processing Pipeline

#### Image Capture

- Use `navigator.mediaDevices.getUserMedia` with `{ video: { facingMode: 'environment' } }` for rear camera
- Capture as JPEG, quality 0.92, max dimension 2048px
- Client-side: dimensions > 1000px shortest side, blur detection, < 10MB

#### Upload & Processing

- POST `/api/v1/documents/upload` with multipart/form-data
- Backend: save to GCP Cloud Storage (AES-256 encryption), process via FastAPI BackgroundTasks, poll status every 2s

#### OCR Extraction — Tiered Pipeline (Cloud Vision + GPT)

Our OCR pipeline uses GCP Cloud Vision for text extraction and GPT for intelligent field mapping, giving us a 150x cost advantage over Google's own Document AI W-2 Parser ($0.30/doc vs our ~$0.002/doc):

1. **Preprocessing** (Pillow): auto-rotate via EXIF, contrast normalization, resize to optimal dimensions
2. **Text Extraction** (GCP Cloud Vision `DOCUMENT_TEXT_DETECTION`): returns hierarchical text (pages/blocks/paragraphs/words) with bounding box coordinates. $0.0015/page, 1K free pages/mo. Google does NOT store images or use them for training.
3. **SSN Isolation** (local regex): SSN extracted via regex (`\d{3}-?\d{2}-?\d{4}`) from Cloud Vision text output ON OUR SERVER. Masked placeholder (XXX-XX-XXXX) replaces SSN in all text sent to OpenAI. SSN never touches any third-party AI API.
4. **Field Mapping — Primary Path** (GPT-4o-mini structured output): send scrubbed OCR text + bounding box positions to GPT-4o-mini. It maps text to a W-2 Pydantic schema with guaranteed valid JSON. Cost: ~$0.001/doc
5. **Field Mapping — Fallback Path** (GPT-4o vision): for low-confidence extractions (<85%), send actual image to GPT-4o vision for direct field extraction. Cost: ~$0.02/doc
6. **Post-validation**: SSN format (9 digits), EIN format (XX-XXXXXXX), wage amounts numeric, cross-field consistency checks
7. **Manual entry fallback**: if both paths produce low-confidence results, flag fields for user manual entry

**IMPORTANT — Accuracy Validation Required:** Cloud Vision basic OCR + GPT-4o-mini field mapping has NOT been validated on real W-2 images. Google recommends their $0.30/doc Document AI W-2 Parser for tax forms. Our tiered approach must be tested with 20+ real W-2 images during Sprint 2. If Tier 1 accuracy < 95%, increase GPT-4o vision fallback usage (still cheaper than any alternative).

- Confidence: field-level confidence from GPT structured output for critical fields
- Mock mode when OPENAI_API_KEY not set — returns realistic hardcoded W2 data. Essential for dev.
- GPT-4o for AI insights generation (where quality matters more than cost)

### 4.2 Tax Calculation Engine

#### Tax Data Source

IRS Revenue Procedure 2024-40 as amended by P.L. 119-21 (One Big Beautiful Bill). Stored in `tax-data/2025.json` with source citations. Validated against IRS Publication 17 worked examples.

#### Federal Tax (2025 Tax Year)

STANDARD DEDUCTIONS (per P.L. 119-21):

- single: $15,750
- married_joint: $31,500
- married_separate: $15,750
- head_of_household: $23,625

TAX BRACKETS (2025, single, per Rev. Proc. 2024-40):

- 10%: $0 — $11,925
- 12%: $11,926 — $48,475
- 22%: $48,476 — $103,350
- 24%: $103,351 — $197,300
- 32%: $197,301 — $250,525
- 35%: $250,526 — $626,350
- 37%: $626,351+

ALL VALUES IN CENTS. Integer arithmetic only. No floats.

#### 2025 Tax Law Changes

- SALT deduction cap: $10,000 → $40,000 (Phase 2 state calculations)
- Overtime pay deduction: up to $12,500 single / $25,000 MFJ (2025-2028, Phase 2)
- Standard deductions increased per One Big Beautiful Bill

### 4.3 Security Requirements

- TLS 1.3 in transit, AES-256 at rest
- Application-level encryption for SSNs (separate key)
- GCP Cloud Storage lifecycle policy: auto-delete after 24 hours
- SSN never sent to any third-party API — extracted locally via regex, masked before GPT processing
- PII-scrubbing middleware on all log output
- HTTP-only, Secure, SameSite=Lax cookies + CSRF tokens
- Rate limiting: 5 req/min auth, 20 req/min upload, 5 uploads/day/user
- hCaptcha on sign-up
- Never validate SSN against external sources
- Account deletion from day one (CCPA/GDPR) — cascades across Neon DB, GCP Cloud Storage, and Upstash sessions

### 4.4 E-File Strategy

#### NORTH STAR: Own IRS MeF Transmitter (January 2027)

The #1 long-term strategic priority. Owning our e-file infrastructure means $0/return cost, full control, and no third-party dependencies. This is what makes "free forever" permanently sustainable.

**IRS Certification Timeline (hard calendar constraints):**

1. **March 2026 (NOW):** Apply for EFIN (Form 8633). Requirements: PTIN, IRS e-Services account, ID.me verification, fingerprinting. 45-day processing. Approval expected ~late April.
2. **May 2026:** EFIN approved. Apply for e-Services MeF system access (1-2 weeks).
3. **May-September 2026:** Build MeF XML generator from TaxCalculation data model (IRS Publication 4164 specification). Map all 1040 fields to MeF XML schema. 4-8 weeks focused engineering.
4. **October 2026:** IRS Assurance Testing System (ATS) opens. Submit 12 mandatory test scenarios. **This is the hard constraint** — ATS opens once per year in October. Missing this window delays go-live by a full year.
5. **November 2026:** Complete communication test with IRS MeF production system.
6. **January 2027:** Production go-live. Free e-file for all users. Deprecate Column Tax for simple returns.

#### Interim: Column Tax SDK (October - December 2026)

While our MeF transmitter goes through IRS certification, Column Tax provides e-file capability:

- Integrate Column Tax web SDK into post-summary flow
- **Transparent cost-passthrough**: user pays exactly what we pay Column Tax (no markup). Target: negotiate to $10-15/return.
- Free PDF download always available as alternative
- User-facing messaging: "We're going through the rigorous IRS e-file certification process, which completes this fall. Until then, you can download your return for free, or e-file through our certified partner at cost. Once we're IRS-certified, e-file will be free forever."

#### MVP (Now - September 2026)

- No e-file. Generate 1040 PDF with step-by-step mailing instructions.
- Include IRS Free File guidance where applicable.
- Messaging: "E-file coming October 2026. Download your completed return now."

### 4.5 1040 PDF Generation

- @react-pdf/renderer for IRS Form 1040 layout
- Cover page with filing instructions
- Match official field positions, Courier font for data
- Footer: "Prepared by FileFree (filefree.tax)"

---

## 5. Data Models

### User

- id: UUID
- email: string (unique, indexed)
- password_hash: string
- full_name_encrypted: string
- referral_code: string (unique)
- referred_by: FK → User (nullable)
- role: enum (user, admin)
- advisor_tier: enum (free, premium) — default: free
- created_at, updated_at: timestamp

### Filing

- id: UUID
- user_id: FK → User
- tax_year: integer
- filing_status: enum
- status: enum (draft, documents_uploaded, data_confirmed, calculated, review, submitted, accepted, rejected)
- created_at, updated_at, submitted_at: timestamp

### Document

- id: UUID
- filing_id: FK → Filing
- document_type: enum (w2, drivers_license, 1099_misc, 1099_nec)
- storage_key: string (encrypted)
- extraction_status: enum (pending, processing, completed, failed)
- extraction_data: JSONB (encrypted)
- confidence_scores: JSONB
- created_at, processed_at: timestamp

### TaxProfile

- id: UUID
- filing_id: FK → Filing (unique)
- ssn_encrypted, full_name_encrypted, address_encrypted, date_of_birth_encrypted: string/JSONB
- total_wages, total_federal_withheld, total_state_withheld: integer (cents)
- state: string
- created_at: timestamp

### TaxCalculation

- id: UUID
- filing_id: FK → Filing (unique)
- adjusted_gross_income, standard_deduction, taxable_income, federal_tax, state_tax, total_withheld, refund_amount, owed_amount: integer (cents)
- ai_insights: JSONB
- calculated_at: timestamp

### Submission

- id: UUID
- filing_id: FK → Filing (unique)
- transmitter_partner: string
- submission_id_external: string
- irs_status: enum (submitted, accepted, rejected)
- rejection_codes: JSONB (nullable)
- submitted_at, status_updated_at: timestamp

### Waitlist

- id: UUID
- email: string (unique)
- source: string (landing, referral, social)
- created_at: timestamp

---

## 6. API Endpoints (MVP)

### Auth

- POST /api/v1/auth/register — hCaptcha verified
- POST /api/v1/auth/login — set session cookie
- POST /api/v1/auth/logout — clear session
- GET /api/v1/auth/me — current user
- DELETE /api/v1/auth/account — delete all data (CCPA)

### Filings

- POST /api/v1/filings — create
- GET /api/v1/filings — list
- GET /api/v1/filings/{id} — detail
- PATCH /api/v1/filings/{id} — update

### Documents

- POST /api/v1/documents/upload — authenticated upload
- GET /api/v1/documents/{id}/status — poll extraction
- GET /api/v1/documents/{id}/data — extraction data
- PATCH /api/v1/documents/{id}/data — user corrections
- POST /api/v1/documents/demo-upload — anonymous try-before-signup (rate limited)

### Tax

- GET /api/v1/filings/{id}/profile — tax profile
- PUT /api/v1/filings/{id}/profile — update profile
- POST /api/v1/filings/{id}/calculate — trigger calculation
- GET /api/v1/filings/{id}/calculation — results
- GET /api/v1/filings/{id}/pdf — download 1040 PDF

### Waitlist

- POST /api/v1/waitlist — join waitlist

### Submission (October 2026+)

- POST /api/v1/filings/{id}/submit — e-file via partner
- GET /api/v1/filings/{id}/submission — status

---

## 7. Revenue Model — The Real Business

### The Core Insight

Free tax filing is the **acquisition channel**, not the product. The monetization event is the **refund moment** — the instant a 22-year-old sees "$3,400 refund" on screen is the highest-intent financial decision moment of their year. That's when we present personalized, genuinely helpful financial product recommendations. Filing earns trust. The refund moment converts trust into revenue.

This is the Credit Karma playbook ($7.1B acquisition by Intuit). Free service, monetized through financial product recommendations powered by the user's actual financial data. Our advantage over Credit Karma: we have W-2 income, exact refund amount, filing status, and state — the most valuable targeting data in consumer finance.

### Free Forever (Acquisition Layer)

- Federal tax preparation — free
- State tax preparation (top 5 income-tax states) — free
- All filing statuses, up to 3 W2s — free
- AI-powered OCR (Cloud Vision + GPT pipeline) + plain-English explanation — free
- 1040 PDF download — free
- E-file via own MeF transmitter (January 2027+) — free
- E-file via Column Tax (October-December 2026) — at cost (passthrough, ~$10-15, no markup). User messaging: "We're completing IRS certification. E-file at cost until then, or download PDF free."
- **Free forever guarantee on /pricing page** — this is the anti-TurboTax move. Core filing is free. E-file becomes free once our IRS certification is complete.

### Revenue Stream 1: Refund Routing to Partner Accounts (PRIMARY — $50-100/funded account)

The #1 revenue stream. After calculating the refund, we show a "Refund Plan" screen:

> "Your refund is $3,412. Where should it go?"
> - Put $1,000 in a 5.5% APY savings account (earn $55 by next tax season) [Partner: Marcus/Wealthfront/Betterment]
> - Open a Roth IRA with $500 (your future self will thank you) [Partner: Wealthfront/Fidelity]
> - Keep the rest in your checking account

IRS Form 8888 allows splitting a refund into up to 3 accounts. We pre-fill this form with the user's allocation choices and include it in the e-file or PDF.

Revenue: HYSA partners pay $50-100 per funded account (Marcus by Goldman Sachs pays $50-100 per referral, per their current program). Investment account partners pay $50-150.

**Why this works:** TurboTax does exactly this — they push Credit Karma Money accounts at refund time. Intuit reported that "faster access to refunds" drove higher average revenue per return (ARPR) in Q3 FY2025. We're doing the same thing without the ecosystem lock-in.

Evidence: Credit Karma model (140M users, $7.1B acquisition). Marcus referral program ($50-100/signup, public data). Wealthfront/Betterment affiliate programs ($50-150/funded account).

Projected conversion: 8-12% of users with refunds route to a partner account. At $75 average payout = **$4.00-6.00/user**.

### Revenue Stream 2: Financial Product Referrals ($50-200/referral)

Post-filing recommendations based on the user's actual tax data. A 22-year-old who just filed their first return is extremely valuable to financial services companies.

Recommendations are personalized and data-driven, not banner ads:
- "You're getting a $2,400 refund — that means you're overpaying by $200/month. Adjust your W-4 and put the difference in a HYSA earning 5.5%."
- "You made $54K. Contributing $3,000 to a Traditional IRA by April 15 would save you $660 in taxes. Here's how."
- High-yield savings accounts: $50-100/referral (Marcus, Wealthfront)
- Roth IRA / investment accounts: $50-150/referral (Fidelity, Wealthfront, Betterment)
- Credit cards (secured or starter): $50-100/approval (NerdWallet model)
- Renters insurance: $30-50/referral (Lemonade)

Evidence: Credit Karma earns commission on every financial product approval. NerdWallet (public company) ARPU is ~$4/user purely on financial referrals. Standard fintech affiliate programs pay $25-150 per qualified signup (Vellko, ContentBase 2026 data).

Projected conversion: 2-4% effective referral rate (10-15% click-through, 20-30% complete signup). At $75 average = **$1.50-3.00/user**.

### Revenue Stream 3: Refund Advance ($3-5/advance revenue share)

Partner with a fintech lender (Refundo, Green Dot, Republic Bank). "Get your refund in 24 hours instead of 21 days." $0 cost to user, 0% APR — the lender makes money on the float and interchange from the prepaid card. We earn $3-5 per advance.

21% of Gen Z rely on their refund for rent and groceries (LendEDU). Speed matters intensely.

Evidence: Refundo charges $50-75 per advance to tax preparers. TurboTax offers advances up to $4,000 via Credit Karma Money. The B2B2C rev share for an app like ours is typically $3-5 per advance.

Projected conversion: 10-15% of filers with refund. At $3-5 = **$0.30-0.75/user**. Requires e-file capability (available October 2026+).

### Revenue Stream 4: Audit Shield ($19-29/year)

AI-assisted audit response preparation + $1M coverage via insurance partner. Positioned as "peace of mind" upsell after filing. This is an anxiety purchase — 52% of Gen Z fear making errors.

Evidence: TurboTax Max offers similar audit defense. TaxAct includes basic audit risk in paid tiers. Actual IRS audit rate is <1%, but the fear factor drives purchases. Attach rates estimated 2-4% based on industry patterns.

Projected conversion: 2-4% of filers. At $19-29 = **$0.38-1.16/user**.

### Revenue Stream 5: Tax Optimization Plan ($29/year, annual — NOT monthly subscription)

Annual one-time purchase at filing time. Personalized year-round tax optimization based on the user's filing data:

- W-4 adjustment calculator ("stop overpaying $200/month to the IRS")
- IRA contribution optimizer ("contribute $3,000 by April 15 to save $660")
- Year-over-year comparison when they file next year
- Quarterly tax estimate reminders (for gig income, Phase 2)
- Priority support during tax season

**Why annual and not monthly:** Tax advice is seasonal. Gen Z won't pay $9.99/month for something they think about once a year. $29/year anchored to filing time is an easier purchase — less than the cost of one TurboTax filing. If the W-4 adjustment alone saves the user $200/year, the ROI is obvious.

Evidence: Gen Z spends 3x more on subscriptions than older generations (Visa 2025). But financial app subscriptions specifically have low conversion — Mint Premium achieved ~2-3%. YNAB ($14.99/mo) works because it's daily-use. Annual pricing at filing time removes the monthly commitment friction.

Projected conversion: 2-5% of filers. At $29 = **$0.58-1.45/user**.

### Revenue Stream 6: Complex Filing ($39 one-time, Phase 2+)

1099 income, itemized deductions, investment income, multi-state filing. Core simple filing stays free forever. Complex situations are paid.

Evidence: FreeTaxUSA charges $14.99 for state. TaxAct charges $39.99-74.99 for complex federal. This is the standard industry monetization.

Projected conversion: 1-5% of users (growing as we add features). At $39 = **$0.39-1.95/user**.

### Revenue Stream 7: B2B Embedded Tax API (Phase 3, 2028+)

april proved this market exists ($78M raised, 30+ fintech partners). License our OCR + calculation + MeF submission engine to fintechs, payroll providers, and neobanks. API pricing $5-25 per return processed (volume-tiered).

Evidence: april (B2B embedded tax, $78M raised). Avalara ($8B company, sales tax API). Column Tax (30+ partners).

### Unit Economics

**Cost per user (verified, v6.0 — Cloud Vision + GPT pipeline):**

| Component | Cost | Source |
|---|---|---|
| GCP Cloud Vision OCR | $0.002 | $0.0015/page, first 1K pages/mo free |
| GPT-4o-mini field mapping (structured) | $0.001 | ~1500 tokens structured output per doc |
| GPT-4o vision fallback (~10% of docs) | $0.002 | $0.02/doc x 10% escalation rate |
| GPT-4o insights generation | $0.040 | $2.50/M input, ~3K in + 2K out |
| GCP Cloud Storage (24 hours) | $0.001 | Negligible |
| Vercel Pro (amortized) | $0.010 | $20/mo / 2000 users |
| Render Starter (amortized) | $0.004 | $7/mo / 2000 users |
| **Total per user** | **$0.060** | |

Version history: v1.0 was $3.30/user (AWS Textract). v4.0 was $0.068/user (PaddleOCR + Render Standard). v5.0/v6.0 is $0.060/user (Cloud Vision + Render Starter) — a **55x cost reduction** from v1.0 through architectural decisions. Cloud Vision has no hosting overhead, unlike PaddleOCR which required a $25/mo instance for its 500MB-2GB+ RAM footprint.

### Three Revenue Scenarios (at 100K users)

**Scenario A — Conservative (referrals only, no lending partner):**

| Stream | Attach Rate | Revenue/User | Annual Revenue |
|---|---|---|---|
| Refund routing to HYSA | 5% | $2.50 | $250K |
| Financial referrals ($75 avg) | 2% | $1.50 | $150K |
| Audit Shield ($19) | 2% | $0.38 | $38K |
| **Blended ARPU** | | **$4.38** | **$438K** |

**Scenario B — Moderate (partnerships in place, validated product):**

| Stream | Attach Rate | Revenue/User | Annual Revenue |
|---|---|---|---|
| Refund routing to HYSA | 8% | $4.00 | $400K |
| Financial referrals ($75 avg) | 3% | $2.25 | $225K |
| Refund advance ($3) | 12% | $0.36 | $36K |
| Audit Shield ($19) | 3% | $0.57 | $57K |
| Tax Optimization Plan ($29/yr) | 3% | $0.87 | $87K |
| **Blended ARPU** | | **$8.05** | **$805K** |

**Scenario C — Aggressive (full stack + B2B):**

| Stream | Attach Rate | Revenue/User | Annual Revenue |
|---|---|---|---|
| Refund routing to HYSA | 10% | $5.00 | $500K |
| Financial referrals ($75 avg) | 4% | $3.00 | $300K |
| Refund advance ($5) | 15% | $0.75 | $75K |
| Audit Shield ($29) | 4% | $1.16 | $116K |
| Tax Optimization Plan ($29/yr) | 5% | $1.45 | $145K |
| Complex filing ($39) | 5% | $1.95 | $195K |
| B2B API ($10/return, 20K returns) | N/A | +$200K | $200K |
| **Consumer ARPU** | | **$13.31** | **$1.331M + $200K B2B** |

**Unit economics (Scenario B, moderate):**

- Cost per user: $0.060
- Blended ARPU: $8.05
- Gross margin: 99.3%
- LTV (5-year, 80% retention): $8.05 x 3.36 = **$27.05**
- Maximum sustainable CAC: $27.05 / 3 = **$9.02**
- Organic/viral acquisition is the primary strategy. Paid ads for boost cycles on proven content only.

### Path to $1M ARR

| Year | Users | Scenario A | Scenario B | Scenario C | Primary Channel |
|---|---|---|---|---|---|
| 2026 | 500 | $0 | $0 | $0 | Beta — validation year |
| 2027 | 30,000 | $131K | $242K | $399K | SEO + social + referral |
| 2028 | 100,000 | $438K | $805K | $1.53M | + B2B API + complex filing |
| 2029 | 200,000 | $876K | $1.61M | $3.06M | Compounding retention + expansion |

Scenario B crosses $1M ARR at ~125K users (mid-2028). Scenario C crosses $1M at ~75K users + B2B (early 2028). Scenario A needs ~230K users (2029).

The 80% retention rate (PCMag industry data) is the engine: 30K users in 2027 -> 24K retained + 76K new = 100K in 2028 -> 80K retained + 120K new = 200K in 2029.

---

## 8. Legal & Compliance

### Immediate Actions (This Week)

- **Apply for EFIN (Form 8633)** — requires PTIN, IRS e-Services account, ID.me verification, fingerprinting. 45-day approval. Start NOW.
- Draft privacy policy (plain English, CCPA/GDPR compliant)
- Draft terms of service with tax preparation disclaimers
- Register business entity if not already done

### MVP Disclaimers

- "FileFree prepares your tax return. E-file submission coming October 2026."
- "FileFree is not a registered tax advisor. This tool is for informational and educational purposes."
- Financial product referrals: clear disclosure that FileFree receives compensation for referrals

### Regulatory Considerations

- AI Tax Advisor: carefully distinguish between "tax information/education" and "tax advice." Tax advice requires CPA/EA license in most states. Position as "personalized tax education" not "advice."
- Financial product referrals: requires clear affiliate disclosures per FTC guidelines
- Refund advance: partner must hold appropriate lending licenses
- Data retention: CCPA right to delete, GDPR compliance for any international users

---

## 9. Realistic Timeline

### March 8 - March 22 (2 weeks): Landing Page + Email Capture

- Landing page with waitlist
- Email capture for "early access"
- Apply for EFIN
- Social media accounts created, first content posted
- **Goal: start building the list before April 15 anxiety peak**

### March 22 - April 15 (3.5 weeks): Try-Before-Signup OCR Demo

- Camera component + image quality checks
- Backend OCR pipeline (Cloud Vision + GPT-4o-mini structured outputs)
- Try-before-signup flow: snap W2 → see extracted data → "Sign up to continue"
- This is live on filefree.tax for the April 15 wave
- **Goal: capture emails from the April 15 traffic spike, validate OCR quality**

### April 15 - May 31 (6.5 weeks): Full MVP

- Auth system, filing flow, data confirmation
- Tax calculator (100% test coverage)
- Return summary with AI insights
- 1040 PDF generation
- Mobile polish, error handling
- Production deployment
- **Goal: 500 beta users from extension filers who haven't filed yet**

### June - September 2026: E-File Integration + Growth + MeF Build

- Integrate Column Tax SDK for interim e-file (cost-passthrough)
- Build own MeF XML generator (IRS Pub 4164) — NORTH STAR work begins
- State tax calculation (CA, NY, IL, PA, OH)
- Referral system + viral tax receipt card
- SEO content (3-5 guides)
- Email lifecycle
- AI Advisor MVP (monthly email tips based on filing data)
- **Goal: ready for October extension deadline with e-file**

### October 2026: Extension Season Launch + ATS Testing

- Live e-file via Column Tax for extension filers (cost-passthrough)
- IRS ATS testing begins for own MeF transmitter (12 test scenarios)
- Full marketing push
- **Goal: 2,000+ extension season filers, validate e-file pipeline, pass ATS**

### January 2027: Full Season Launch — FREE E-FILE (NORTH STAR)

- Own MeF transmitter goes live — e-file is FREE for all users
- Deprecate Column Tax for simple returns
- Product Hunt + Hacker News launch
- TikTok/YouTube content campaign
- AI Advisor subscription launch
- Financial product referral partnerships live
- **Goal: 50,000 filers with free e-file**

---

## 10. Content & Distribution Strategy

### Why This Matters

At $11.38 max CAC, we cannot afford paid acquisition at scale. Organic and viral channels are existential, not optional. The content-to-viral flywheel is: create organic content -> boost winners with paid ads -> convert to demo -> user files -> shares tax receipt card -> new organic reach.

### Tooling Stack

- **Postiz** (self-hosted, open-source): Social media scheduling across 28+ platforms. Runs on dedicated Hetzner VPS ($7.50/mo) alongside n8n. REST API for programmatic scheduling.
- **n8n** (self-hosted, open-source): Autonomous workflow automation. Runs on same VPS. Automates daily content drafting, weekly analytics review, and monthly cost monitoring — using persona system prompts from `.cursor/rules/*.mdc`.
- **CapCut** (free): Video editing for short-form content
- **TikTok Ads Manager + Meta Ads Manager**: Paid amplification on proven organic content

### SEO (Long-term compounding)

- Target: "how to file taxes for free", "what is a W2", "standard deduction 2025", "first time filing taxes", "tax refund calculator"
- 3-5 genuinely helpful guides at launch, add 2/month
- FAQ schema markup for featured snippets
- "First Time Filing" hub page — this is our beachhead keyword cluster

### Social Media (Gen Z native channels — see social.mdc for full playbook)

- TikTok (primary) + Instagram Reels + YouTube Shorts + X: 7-10 posts/week during tax season, 2-3/week off-season
- 5 content pillars: tax myths busted, "I filed in X minutes" reactions, W-2 explainers, money tips for Gen Z, founder journey (build-in-public)
- Founder-led content — overproduced is death on TikTok. Authentic > polished.
- Creator partnerships: 10 micro-influencers (10K-100K followers), free product + UTM-tracked rev share
- Content repurposing: one video becomes TikTok + Reel + Short + X clip + blog excerpt

### Paid Amplification ($200-500/mo tax season only)

- **TikTok Spark Ads** (primary, $3-10 CPM): Boost organic posts with >1K views. Engagement persists permanently. Intermittent 3-5 day bursts at $20-50/day, 2-3 cycles/month.
- **Meta/Instagram Boost** (secondary, $8-12 CPM): Boost top Reels. Better targeting for retargeting TikTok viewers.
- **Key rule**: Never create ad-first content. Only boost posts the algorithm already validated organically.
- **Kill criteria**: TikTok CPC > $0.50 after $20 spend = stop. Meta CPC > $1.00 after $15 spend = stop.
- Off-season (May+): $0 paid. Organic only.

### Viral Loops

- Tax receipt card (shareable filing summary): target 15% share rate. Formats: IG Story (1080x1920), X (1200x675), square (1080x1080).
- Referral program: "Share FileFree" from dashboard, track with unique codes + UTM
- Try-before-signup: the demo IS the marketing — people share the "wow" moment

### Community

- r/personalfinance, r/tax, r/GenZ — be genuinely helpful, not promotional
- "Free tax help" positioning on Twitter/X during tax season
- College campus partnerships (financial literacy programs)

### PR

- Product Hunt launch (January 2027 filing season)
- Hacker News "Show HN" (technical audience, high-quality early adopters)
- "Gen Z tax anxiety" angle for lifestyle/finance press

### Autonomous Content (Phase 2, May+)

n8n workflows automate the content pipeline using persona system prompts:
- Daily: auto-draft 3 posts from trending topics via OpenAI + social.mdc prompt -> queue in Postiz as drafts -> founder reviews/approves (5 min)
- Weekly: pull Postiz analytics -> OpenAI generates growth report via growth.mdc prompt -> email summary
- Monthly: pull infrastructure costs -> OpenAI checks vs budget via cfo.mdc prompt -> alert if overspending

