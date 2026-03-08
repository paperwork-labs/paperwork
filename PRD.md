# filefree.tax — Product Requirements Document
**Version**: 1.0
**Last Updated**: 2026-03-08
**Status**: MVP Definition

---

## 1. Product Overview

### 1.1 Problem Statement
~150 million individual tax returns are filed annually in the US. Approximately 70% of filers have simple tax situations (W2 income, standard deduction), yet they pay $0–$170+ to TurboTax or spend hours at H&R Block for what should be a 5-minute process. The tax filing process is intentionally complex to justify software fees. Users with a single W2 taking the standard deduction should be able to file by taking two photos.

### 1.2 Solution
filefree.tax is a mobile-first web application that lets users file their federal (and state) tax returns by photographing their W2 and Driver's License. AI extracts all necessary data, calculates the return, provides a plain-English summary, and e-files with the IRS — all in under 60 seconds.

### 1.3 Target User (MVP)
- Age 18-35
- Single filer OR Married filing jointly
- W2 income only (1-2 W2s)
- Standard deduction (no itemizing)
- No dependents (MVP), add dependents in v1.1
- No investment income, rental income, or self-employment (MVP)
- US resident, single state

### 1.4 Success Metrics
- Time to file: < 90 seconds from first photo to submission
- OCR accuracy: > 98% field-level accuracy on W2 extraction
- User completion rate: > 70% of users who start filing complete it
- NPS: > 60

---

## 2. User Flow (MVP)

### Screen 1: Landing / Login
- Hero: "File Your Taxes for Free. Just Take a Photo."
- CTA: "Start Filing — It's Free"
- Social proof: filing counter, testimonials
- Auth: Email + password, or Google OAuth
- Mobile-optimized, dark theme with gradient accents
- Brand: filefree.tax logo, minimal nav

### Screen 2: Document Capture — W2
- Full-screen camera interface with W2 bounding box overlay
- Guide text: "Position your W2 within the frame"
- Auto-capture when document is detected and aligned (stretch goal)
- Manual capture button as fallback
- Immediate quality check: blur detection, lighting check
- If quality fails: "That's a bit blurry. Try again with more light."
- Support for uploading from photo library as alternative
- Multiple W2 support (show "Add another W2" after first)

### Screen 3: Document Capture — Driver's License
- Same camera interface, DL-shaped bounding box
- Front of DL only (MVP)
- Extract: Full name, address, DOB, DL number
- Used for identity verification, not tax data

### Screen 4: Confirm Extracted Data
- Show extracted data in clean, editable form
- Fields from W2: Employer name, EIN, Wages (Box 1), Federal Tax Withheld (Box 2), State (Box 15), State Wages (Box 16), State Tax Withheld (Box 17), SSN
- Fields from DL: Full name, Address (street, city, state, zip), DOB
- Confidence indicators on each field (green = high confidence, yellow = please verify)
- User can tap any field to edit
- "Everything look right?" CTA at bottom

### Screen 5: Filing Details
- Filing status selector (Single, MFJ, MFS, HoH, QSS) — AI pre-selects based on data
- Standard deduction auto-selected (show amount)
- Option to add dependents (v1.1, greyed out in MVP with "Coming Soon")
- Any additional questions IRS requires (healthcare coverage, etc.)
- Keep this screen MINIMAL — only ask what's legally required

### Screen 6: Your Return Summary
- THIS IS THE MONEY SCREEN — make it beautiful
- Big animated refund amount (or amount owed) with celebration animation if refund
- Breakdown:
  - Gross Income: $XX,XXX
  - Standard Deduction: -$XX,XXX
  - Taxable Income: $XX,XXX
  - Federal Tax: $X,XXX
  - Already Paid (Withheld): $X,XXX
  - **Your Refund: $X,XXX** (or Amount Owed)
- Visual: Pie chart showing "Where your taxes go" (defense, healthcare, education, etc.)
- Visual: Bar chart comparing "Your refund vs. average in your state"
- AI Insights section (STREAMS IN with typewriter effect):
  - Plain-English explanation: "You earned $54,000 and already paid $6,200 in taxes through your paycheck. You only owed $4,800, so the IRS owes you $1,400 back."
  - Any missed opportunities: "Did you know? If you contributed to a Traditional IRA, you could have saved up to $X more."
- CTA: "File Now — Free" for federal, "Add State Filing — $14.99"

### Screen 7: E-File Confirmation
- Review final return summary (condensed)
- E-sign with IRS PIN or AGI from last year
- Terms acceptance
- Submit button with satisfying animation
- After submission: "Your return has been submitted to the IRS! 🎉"
- Expected refund date estimate
- Option to set up refund tracking notifications
- Upsell: "Get your refund up to 5 days early" (refund advance partner)
- Upsell: "Protect yourself with Audit Shield — $29/year"

### Screen 8: Dashboard (Post-Filing)
- Filing status tracker (Submitted → Accepted → Processing → Refund Sent)
- IRS refund status integration (Where's My Refund API)
- Download copy of return (PDF)
- Amendment flow (if needed)
- "File [State] Return" CTA if they only did federal

---

## 3. Technical Requirements

### 3.1 Document Processing Pipeline

#### Image Capture
- Use `navigator.mediaDevices.getUserMedia` with `{ video: { facingMode: 'environment' } }` for rear camera
- Render video stream to canvas element for preview
- Capture frame as JPEG, quality 0.92, max dimension 2048px
- Client-side checks before upload:
  - Image dimensions > 1000px on shortest side
  - Basic blur detection via Laplacian variance on canvas pixel data
  - File size < 10MB

#### Upload & Processing
- POST `/api/v1/documents/upload` with multipart/form-data
- Fields: `file` (image), `document_type` (w2 | drivers_license), `filing_id`
- Backend flow:
  1. Save to S3 with server-side encryption (AES-256)
  2. Kick off Celery task for async processing
  3. Return `{ document_id, status: 'processing' }`
  4. Client polls `GET /api/v1/documents/{id}/status` every 2 seconds

#### OCR Extraction (Celery Task)
- Call AWS Textract `analyze_document` with FeatureTypes=['FORMS']
- Parse Textract response to extract key-value pairs
- Map W2-specific fields:
  - Box a: Employee SSN
  - Box b: Employer EIN
  - Box c: Employer name and address
  - Box e: Employee name
  - Box f: Employee address
  - Box 1: Wages, tips, other compensation
  - Box 2: Federal income tax withheld
  - Box 3: Social security wages
  - Box 4: Social security tax withheld
  - Box 5: Medicare wages and tips
  - Box 6: Medicare tax withheld
  - Box 15: State
  - Box 16: State wages
  - Box 17: State income tax withheld
- Post-process with LLM validation:
  - System prompt validates and corrects OCR errors
  - Ensures SSN format, EIN format, valid monetary values, valid state abbreviations
  - Returns structured JSON with per-field confidence scores
- Store extraction results in database

### 3.2 Tax Calculation Engine

#### Federal Tax Calculation (2025 Tax Year)

INPUTS:
  - wages: integer (cents) — from W2 Box 1
  - federal_withheld: integer (cents) — from W2 Box 2
  - filing_status: enum (single, married_joint, married_separate, head_of_household)

STANDARD DEDUCTIONS (2025):
  - single: $15,000 (UPDATE WITH ACTUAL IRS NUMBERS WHEN RELEASED)
  - married_joint: $30,000
  - married_separate: $15,000
  - head_of_household: $22,500

TAX BRACKETS (2025, single):
  - 10%: $0 — $11,925
  - 12%: $11,926 — $48,475
  - 22%: $48,476 — $103,350
  - 24%: $103,351 — $197,300
  - 32%: $197,301 — $250,525
  - 35%: $250,526 — $626,350
  - 37%: $626,351+
  (STORE ALL BRACKET TABLES FOR ALL FILING STATUSES)

CALCULATION:
  1. adjusted_gross_income = sum(all_w2_wages)
  2. standard_deduction = lookup(filing_status)
  3. taxable_income = max(0, adjusted_gross_income - standard_deduction)
  4. federal_tax = apply_brackets(taxable_income, filing_status)
  5. total_withheld = sum(all_w2_federal_withheld)
  6. refund_or_owed = total_withheld - federal_tax
  7. if refund_or_owed > 0: user gets refund
  8. if refund_or_owed < 0: user owes

#### State Tax Calculation (Phase 2)
- Start with: CA, NY, IL, PA, OH (highest pop states with income tax)
- No-income-tax states (TX, FL, WA, NV, etc.): auto-detect and skip
- Each state is a pluggable module with its own brackets and rules

### 3.3 Security Requirements
- All data encrypted in transit (TLS 1.3) and at rest (AES-256)
- SSNs encrypted with application-level encryption (separate key from DB encryption)
- W2 images deleted from S3 within 24 hours of successful extraction
- No PII in application logs (use correlation IDs)
- Session-based auth with HTTP-only, Secure, SameSite=Strict cookies
- CSRF protection on all state-changing endpoints
- Rate limiting: 5 requests/min on auth endpoints, 20 requests/min on upload endpoints
- SOC 2 Type II compliance (target for post-MVP)
- Annual penetration testing (target for post-MVP)

### 3.4 E-File Integration (MVP uses transmitter partner)
- Partner with an authorized IRS e-file transmitter (Keystone, Drake, etc.)
- Generate IRS MeF-compatible XML from our tax calculation
- Submit via partner API
- Track submission status: Submitted → Accepted/Rejected
- Handle rejection codes and surface user-friendly error messages
- Long-term: Apply for own ERO/transmitter status (IRS Form 8633)

---

## 4. Data Models

### User
- id: UUID
- email: string (unique, indexed)
- password_hash: string
- full_name: string (encrypted)
- created_at: timestamp
- updated_at: timestamp

### Filing
- id: UUID
- user_id: FK → User
- tax_year: integer
- filing_status: enum
- status: enum (draft, documents_uploaded, data_confirmed, calculated, review, submitted, accepted, rejected)
- created_at: timestamp
- updated_at: timestamp
- submitted_at: timestamp (nullable)

### Document
- id: UUID
- filing_id: FK → Filing
- document_type: enum (w2, drivers_license, 1099_misc, 1099_nec, etc.)
- s3_key: string (encrypted)
- extraction_status: enum (pending, processing, completed, failed)
- extraction_data: JSONB (encrypted)
- confidence_scores: JSONB
- created_at: timestamp
- processed_at: timestamp (nullable)

### TaxProfile
- id: UUID
- filing_id: FK → Filing (unique)
- ssn_encrypted: string
- full_name_encrypted: string
- address_encrypted: JSONB
- date_of_birth_encrypted: string
- total_wages: integer (cents)
- total_federal_withheld: integer (cents)
- total_state_withheld: integer (cents)
- state: string
- created_at: timestamp

### TaxCalculation
- id: UUID
- filing_id: FK → Filing (unique)
- adjusted_gross_income: integer (cents)
- standard_deduction: integer (cents)
- taxable_income: integer (cents)
- federal_tax: integer (cents)
- state_tax: integer (cents, nullable)
- total_withheld: integer (cents)
- refund_amount: integer (cents, 0 if owed)
- owed_amount: integer (cents, 0 if refund)
- ai_insights: JSONB
- calculated_at: timestamp

### Submission
- id: UUID
- filing_id: FK → Filing (unique)
- transmitter_partner: string
- submission_id_external: string
- irs_status: enum (submitted, accepted, rejected)
- rejection_codes: JSONB (nullable)
- submitted_at: timestamp
- status_updated_at: timestamp

---

## 5. API Endpoints (MVP)

### Auth
- POST /api/v1/auth/register — Create account
- POST /api/v1/auth/login — Login, set session cookie
- POST /api/v1/auth/logout — Clear session
- GET /api/v1/auth/me — Get current user

### Filings
- POST /api/v1/filings — Create new filing
- GET /api/v1/filings — List user's filings
- GET /api/v1/filings/{id} — Get filing detail
- PATCH /api/v1/filings/{id} — Update filing (filing_status, etc.)

### Documents
- POST /api/v1/documents/upload — Upload document image
- GET /api/v1/documents/{id}/status — Poll extraction status
- GET /api/v1/documents/{id}/data — Get extracted data
- PATCH /api/v1/documents/{id}/data — User corrects extracted data

### Tax Profile
- GET /api/v1/filings/{id}/profile — Get tax profile
- PUT /api/v1/filings/{id}/profile — Update/confirm tax profile

### Tax Calculation
- POST /api/v1/filings/{id}/calculate — Trigger calculation
- GET /api/v1/filings/{id}/calculation — Get calculation results

### Submission
- POST /api/v1/filings/{id}/submit — Submit to IRS via partner
- GET /api/v1/filings/{id}/submission — Get submission status

---

## 6. Revenue Model

### Free Tier
- Federal filing for W2 + standard deduction
- Single or MFJ filing status
- Up to 2 W2s

### Paid Features
- State filing: $14.99 per state
- Refund advance: Revenue share with fintech partner (user gets refund early, partner charges fee)
- Audit Shield: $29/year subscription (AI-assisted audit response + $1M coverage via insurance partner)
- Complex filing upgrade: $39.99 (1099, itemized deductions, investment income) — Phase 2

---

## 7. Phase Roadmap

### MVP (Weeks 1-8)
- Landing page + auth
- W2 photo capture + OCR extraction
- DL photo capture + identity extraction
- Data confirmation screen
- Federal tax calculation (simple filers)
- Return summary with streaming AI insights
- Mock e-file (save return, generate PDF, no actual IRS submission)
- Beautiful, animated UI throughout

### Phase 2 (Weeks 9-16)
- Live e-file via transmitter partner
- State tax calculation (top 5 states)
- Payment integration (Stripe) for state filing
- Refund tracking dashboard
- Multiple W2 support
- Dependent support

### Phase 3 (Weeks 17-24)
- 1099 support (freelancers, contractors)
- Refund advance partnership
- Audit Shield subscription
- Itemized deductions
- Prior year comparison
- PWA (manifest.json, service worker, Add to Home Screen)