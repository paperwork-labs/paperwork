# filefree.tax — Build Tasks

Work through these in order. Each task is scoped for one Cursor session. Paste the task into Cursor as your prompt — it has .cursorrules for full context. Check them off as you go.

---

## Phase 0: Project Setup

Task 0.0 — Dev Infrastructure & Docker
Set up the full local development environment using Docker Compose with separate dev and test configurations so they never share data.

Create three compose files at the project root:

docker-compose.yml — base services shared by both dev and test:

PostgreSQL 15 (user: filefree, password: filefree_dev)
Redis 7
The FastAPI backend (volume-mounted code, hot reload via uvicorn --reload)
A Celery worker (same image as API, runs celery worker command)
A Celery beat scheduler (same image as API, runs celery beat command)
The Next.js frontend (volume-mounted code, hot reload)
Mailhog for dev email testing (SMTP port 1025, UI port 8025)
docker-compose.dev.yml — dev overrides:

Postgres db name: filefree_dev, exposed on port 5432
Redis exposed on port 6379
API exposed on port 8000
Frontend exposed on port 3000
Mailhog UI exposed on port 8025
Named volumes for postgres data persistence (filefree_dev_pgdata) so your data survives restarts
Named volume for redis data persistence
All env vars point to dev database and dev redis (db 0)
docker-compose.test.yml — test overrides:

Postgres db name: filefree_test, use tmpfs for the data directory so it's fast and fully disposable
Redis uses db 1 (or a separate container) so it never touches dev sessions
API and celery run but no ports exposed (tests run inside the network)
No frontend service (not needed for backend tests)
No named volumes — everything is ephemeral
Overrides the API entrypoint to run: alembic upgrade head, then wait (so you can exec pytest into it), OR provide a test-runner service that depends on api+postgres+redis being healthy and runs pytest then exits
Environment variable TESTING=true so the app can detect test mode (e.g., skip real S3, use mock OCR)
Usage patterns (document these in the README):

# Dev
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run tests (isolated, disposable)
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm api pytest -v

# Tear down test containers (no data loss in dev)
docker compose -f docker-compose.yml -f docker-compose.test.yml down

Create Dockerfiles:

filefree-api/Dockerfile — Python 3.11-slim, install requirements, expose 8000
filefree-web/Dockerfile.dev — Node 20-alpine, npm install, expose 3000
All services should have health checks where applicable. Use depends_on with conditions so the API waits for healthy postgres and redis before starting.

Also set up:

.gitignore covering Node, Python, .env files, .next, pycache, venv, docker volumes
.env.example files for both frontend and backend with all required env vars documented (include comments noting which vars differ between dev and test)
A README.md with instructions for both docker compose up commands, what URLs to hit in dev, and how to run tests in isolation
Also create a .github/workflows/ci.yml GitHub Actions workflow that:

On PR and push to main
Uses the test compose configuration (or spins up postgres + redis as GH Actions service containers)
Runs Python linting (ruff), type checking (mypy), and tests (pytest) against the test database
Runs TypeScript linting (eslint), type checking (tsc --noEmit), tests (vitest), and build (next build)
And a .github/dependabot.yml that checks npm, pip, and github-actions weekly.






### Task 0.1 — Initialize Next.js Frontend
Create a new Next.js 14 app inside `filefree-web/` with App Router, TypeScript, Tailwind CSS, ESLint, and src directory.

Install these dependencies:
- framer-motion, recharts, lucide-react, zustand, react-hook-form, @hookform/resolvers, zod, axios
- ai, @ai-sdk/react, @ai-sdk/openai (Vercel AI SDK for streaming)
- @react-pdf/renderer (for tax return PDF generation)
- clsx, tailwind-merge

Initialize shadcn/ui: New York style, Zinc base color, CSS variables enabled. Add these base components: button, card, input, label, form, dialog, sheet, toast, dropdown-menu, separator, badge, tabs.

Configure `tailwind.config.ts`:
- Dark mode: 'class'
- Extend with brand violet/purple palette
- Add Inter (body) and JetBrains Mono (numbers/monospace) fonts

Override CSS variables in `globals.css` for our dark violet/purple theme:
- Background: very deep gray/near-black
- Primary: violet
- Accent: purple tones
- Make it feel like Linear or Raycast, not TurboTax

Create these foundational files:
- `src/lib/api.ts` — axios instance with base URL from env var, withCredentials for cookies, response interceptor for error handling
- `src/lib/utils.ts` — formatCurrency (cents to $X,XXX.XX), formatSSN (mask as XXX-XX-1234), cn (clsx + tailwind-merge)
- `src/types/index.ts` — TypeScript interfaces matching all data models from PRD (User, Filing, Document, TaxProfile, TaxCalculation, Submission, all enums)
- `src/store/use-auth-store.ts` — Zustand store: user, isAuthenticated, login/register/logout actions
- `src/store/use-filing-store.ts` — Zustand store: currentStep, filing, documents, taxProfile, calculation, navigation actions

Base layout in `src/app/layout.tsx`: dark background, fonts loaded, metadata for filefree.tax.

Verify it runs on localhost:3000 with the dark theme.

### Task 0.2 — Initialize FastAPI Backend
Create the `filefree-api/` directory with this structure:
ilefree-api/
├── app/
│ ├── init.py
│ ├── main.py # FastAPI app, CORS, middleware, exception handlers
│ ├── config.py # Pydantic Settings for all env vars
│ ├── database.py # Async SQLAlchemy engine + session maker
│ ├── worker.py # Celery app configuration
│ ├── models/ # SQLAlchemy ORM models
│ │ ├── init.py
│ │ ├── user.py
│ │ ├── filing.py
│ │ ├── document.py
│ │ ├── tax_profile.py
│ │ ├── tax_calculation.py
│ │ └── submission.py
│ ├── schemas/ # Pydantic request/response schemas
│ │ ├── init.py
│ │ ├── auth.py
│ │ ├── filing.py
│ │ ├── document.py
│ │ └── tax.py
│ ├── routers/ # API route handlers
│ │ ├── init.py
│ │ ├── auth.py
│ │ ├── filings.py
│ │ ├── documents.py
│ │ └── tax.py
│ ├── services/ # Business logic layer
│ │ ├── init.py
│ │ ├── auth_service.py
│ │ ├── document_service.py
│ │ ├── ocr_service.py
│ │ ├── tax_calculator.py
│ │ └── ai_insights.py
│ ├── repositories/ # Database access layer
│ │ ├── init.py
│ │ ├── user_repo.py
│ │ ├── filing_repo.py
│ │ └── document_repo.py
│ └── utils/
│ ├── init.py
│ ├── encryption.py # AES-256 encryption for PII fields
│ ├── security.py # Password hashing, session management
│ └── exceptions.py # Custom exception classes + FastAPI handlers
├── alembic/
│ └── versions/
├── alembic.ini
├── tests/
│ ├── init.py
│ ├── conftest.py
│ ├── test_tax_calculator.py
│ └── test_ocr_service.py
├── requirements.txt
└── .env.example

requirements.txt should include: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, python-multipart, python-jose[cryptography], passlib[bcrypt], boto3, openai, redis, celery, pillow, httpx, pytest, pytest-asyncio, ruff, mypy, factory-boy.

Implement:
- `main.py`: FastAPI app with CORS (allow frontend origin from env), include all routers with /api/v1 prefix, register exception handlers, add /health endpoint
- `config.py`: Pydantic Settings reading DATABASE_URL, REDIS_URL, AWS keys, OPENAI_API_KEY, ENCRYPTION_KEY, SECRET_KEY, FRONTEND_URL, S3_BUCKET from env
- `database.py`: async SQLAlchemy engine using asyncpg, async session maker, get_db dependency
- `worker.py`: Celery app configured with Redis broker URL from config
- `utils/exceptions.py`: UnauthorizedError, NotFoundError, ValidationError, ExtractionError — each mapped to proper HTTP status codes in exception handlers

Verify: uvicorn runs and /health returns `{ "status": "healthy" }`.

### Task 0.3 — Database Models & Migrations
Implement all SQLAlchemy ORM models matching the data models from PRD.md Section 4.

Every model needs:
- id: UUID primary key with default uuid4
- created_at: DateTime with server_default=func.now()
- updated_at: DateTime with onupdate=func.now()

Use proper types:
- SQLAlchemy Enum for all status fields (FilingStatus, DocumentType, ExtractionStatus, IrsStatus)
- JSONB for extraction_data, confidence_scores, address_encrypted, ai_insights, rejection_codes
- String for all encrypted fields (SSN, names, etc.)
- Integer for all monetary values (cents)
- Proper foreign key relationships with back_populates

Set up Alembic for async:
- `alembic init alembic`
- Configure env.py to use our async engine and import all models
- Generate initial migration
- The migration should run when the API container starts (or via a manual command)

Verify: all tables are created in the Dockerized postgres.

---

## Phase 1: Auth + Landing Page

### Task 1.1 — Backend Auth System
Implement the full auth system:

`utils/security.py`:
- hash_password and verify_password using bcrypt via passlib
- generate_session_token using secrets.token_urlsafe(32)

`repositories/user_repo.py`:
- create_user(db, email, password_hash, full_name_encrypted)
- get_by_email(db, email)
- get_by_id(db, user_id)

`services/auth_service.py`:
- register(db, redis, email, password, full_name) — validate unique email, hash password, encrypt full_name, create user, create Redis session, return user + session token
- login(db, redis, email, password) — verify credentials, create Redis session, return user + session token
- logout(redis, session_token) — delete Redis session
- get_current_user(db, redis, session_token) — lookup session in Redis, fetch user

Redis sessions: key = `session:{token}`, value = user_id as string, TTL = 7 days.

`routers/auth.py`:
- POST `/api/v1/auth/register` — body: { email, password, full_name }, sets httponly cookie named `session`, returns `{ success: true, data: { id, email } }`
- POST `/api/v1/auth/login` — body: { email, password }, sets cookie, returns user
- POST `/api/v1/auth/logout` — clears cookie, deletes Redis session
- GET `/api/v1/auth/me` — reads cookie, returns current user or 401

Cookie settings: httponly=True, secure=True (except when ENVIRONMENT=development), samesite='lax', max_age=604800, path='/'

Create a FastAPI dependency `get_current_user` that extracts the session cookie, validates against Redis, and returns the User ORM object. Raise UnauthorizedError if invalid.

### Task 1.2 — Landing Page
Create the filefree.tax landing page at `src/app/page.tsx`.

Hero section:
- Headline: "File Your Taxes for Free"
- Subline: "Take a photo of your W2. We'll handle the rest."
- Big CTA button with animated gradient border using Framer Motion: "Start Filing — It's Free"
- Subtle animated background — maybe a slow-moving gradient mesh or floating particles (Framer Motion, nothing heavy)

Social proof: "Join X,XXX people who already filed" with an animated counter

How it works section — 3 steps with Framer Motion scroll-triggered animations:
1. 📸 "Snap your W2" — take a photo
2. ✅ "Confirm your info" — AI extracts everything, you just double-check
3. 🚀 "File instantly" — submitted to the IRS in seconds

Comparison section: "filefree.tax vs TurboTax" — side by side showing time (60s vs 45min), cost (Free vs $89+), questions asked (3 vs 60+)

Footer with links and legal disclaimers.

Use shadcn components (Button, Card) with our dark theme. Must look amazing on mobile (375px) through desktop (1440px). This is the first thing users see — it needs to feel premium, modern, and fast. Think Linear.app or Raycast landing page energy.

### Task 1.3 — Auth UI + Middleware
Create auth pages:

`src/app/auth/layout.tsx` — centered card on gradient background, filefree.tax logo at top

`src/app/auth/register/page.tsx`:
- Fields: Full Name, Email, Password, Confirm Password
- Zod schema validation via shadcn Form component
- Animated field transitions with Framer Motion
- On success: call useAuthStore.register, redirect to /file

`src/app/auth/login/page.tsx`:
- Fields: Email, Password
- "Don't have an account? Sign up" link
- On success: call useAuthStore.login, redirect to /file

Implement `useAuthStore` fully:
- user state, isAuthenticated computed
- register action: POST /api/v1/auth/register, set user state
- login action: POST /api/v1/auth/login, set user state
- logout action: POST /api/v1/auth/logout, clear state
- checkAuth action: GET /api/v1/auth/me, set user or clear (call on app mount)

Create a shadcn Toast-based notification system for errors ("Invalid email or password", "Account already exists", etc.). Never show raw API errors.

Create `src/middleware.ts` (Next.js middleware):
- Protect all `/file/*` and `/dashboard/*` routes
- If no session cookie present, redirect to `/auth/login`
- Allow `/`, `/auth/*`, and API routes through

---

## Phase 2: Document Capture

### Task 2.1 — Camera Component
Create `src/components/camera/document-camera.tsx`.

Props: documentType ('w2' | 'drivers_license'), onCapture (file: File) => void, onError (message: string) => void

The component should:
1. Request rear camera: `navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } } })`
2. Render the live video stream filling the viewport
3. Overlay a semi-transparent dark mask with a document-shaped transparent cutout in the center:
   - W2: landscape rectangle, roughly 8.5x11 aspect ratio
   - DL: landscape rectangle, credit card aspect ratio (~1.586:1)
4. Animated guide text above the cutout: "Position your W2 within the frame"
5. Large capture button centered at bottom — white circle with satisfying scale animation on press (Framer Motion)
6. "Upload from library" text button below capture button — triggers a hidden file input with accept="image/*"
7. On capture: draw current video frame to a hidden canvas, export as JPEG (quality 0.92), create File object, call onCapture

Handle states:
- Loading: "Starting camera..." with spinner while getUserMedia resolves
- Permission denied: friendly message "Camera access is needed to scan your documents. Please allow camera access in your browser settings." with a "Try Again" button
- Error: generic camera error message

Make it feel like a native camera app. Full viewport, no browser chrome showing if possible. Dark UI with white/violet accents.

### Task 2.2 — Image Quality Checks
Create `src/lib/image-quality.ts` with these functions:

`checkBlur(canvas: HTMLCanvasElement): { isBlurry: boolean, score: number }`:
- Convert canvas to grayscale pixel data
- Apply 3x3 Laplacian kernel convolution across the image
- Calculate variance of the Laplacian output
- Return isBlurry: true if variance < 100 (tune threshold as needed)

`checkDimensions(width: number, height: number): boolean`:
- Return false if the shortest side is < 1000px

`checkFileSize(file: File): boolean`:
- Return false if > 10MB

`validateCapturedImage(file: File, canvas: HTMLCanvasElement): { valid: boolean, message?: string }`:
- Run all three checks
- Return first failure with a friendly message:
  - Blurry: "That came out a bit blurry. Try holding your phone steadier."
  - Too small: "Move your phone a bit closer to the document."
  - Too large: "Image is too large. Try again."
- If all pass: { valid: true }

In the DocumentCamera component: after capturing, run validateCapturedImage. If it fails, show the error message with a "Retake" button. If it passes, show the captured image as a preview with "Use This Photo" and "Retake" buttons. "Use This Photo" calls onCapture with the file.

### Task 2.3 — Document Upload Backend
Implement the document upload and retrieval endpoints.

`repositories/document_repo.py`:
- create_document(db, filing_id, document_type, s3_key)
- get_by_id(db, document_id)
- update_status(db, document_id, status)
- update_extraction_data(db, document_id, data, confidence_scores)

`services/document_service.py`:
- upload_document(db, file, document_type, filing_id, user_id):
  1. Verify the filing belongs to the user
  2. Validate file type (JPEG or PNG only)
  3. Process image with Pillow: resize if largest dimension > 2048px, maintain aspect ratio
  4. Upload to S3 with server-side encryption (AES-256), key format: `documents/{filing_id}/{document_id}.jpg`
  5. Create Document record in DB with status='pending'
  6. Enqueue Celery task: process_document.delay(document_id)
  7. Return the Document record
- get_status(db, document_id, user_id) — verify ownership, return status
- get_extraction_data(db, document_id, user_id) — verify ownership, return extraction_data + confidence_scores
- update_extraction_data(db, document_id, user_id, corrections) — merge user corrections into extraction_data

`routers/documents.py`:
- POST `/api/v1/documents/upload` — multipart form: file + document_type + filing_id. Returns `{ success: true, data: { id, status: 'pending' } }`
- GET `/api/v1/documents/{id}/status` — returns `{ success: true, data: { status, extraction_data?, confidence_scores? } }`
- GET `/api/v1/documents/{id}/data` — returns full extraction data
- PATCH `/api/v1/documents/{id}/data` — body: partial extraction data corrections

All endpoints require auth. All endpoints verify the document belongs to the current user's filing.

For S3: create a utility in `services/s3_service.py` that handles upload and presigned URL generation. Use config values for bucket name and region. If AWS creds aren't configured (local dev), save files to a local `uploads/` directory instead as a fallback.

### Task 2.4 — OCR Pipeline (Celery Task)
Implement the document processing Celery task.

`services/ocr_service.py`:

Main Celery task `process_document(document_id: str)`:
1. Fetch Document record from DB
2. Download image from S3 (or local uploads/ in dev)
3. Call AWS Textract `analyze_document` with FeatureTypes=['FORMS']
4. Parse the Textract response — extract all key-value pairs from the FORMS feature results
5. Map extracted pairs to structured fields based on document_type:

For W2:
- Map Box labels (Box 1, Box 2, etc.) to field names (wages, federal_withheld, etc.)
- Extract: employee_ssn, employer_ein, employer_name, employer_address, employee_name, employee_address, wages (Box 1), federal_withheld (Box 2), ss_wages (Box 3), ss_tax (Box 4), medicare_wages (Box 5), medicare_tax (Box 6), state (Box 15), state_wages (Box 16), state_withheld (Box 17)

For DL:
- Extract: full_name, address (street, city, state, zip), date_of_birth, dl_number

6. Send raw extraction to GPT-4o for validation and correction:
- System prompt: "You are a tax document data validator. Given raw OCR output, validate and correct extracted fields. Fix OCR errors (O vs 0, l vs 1). Ensure SSN is 9 digits (XXX-XX-XXXX), EIN is 9 digits (XX-XXXXXXX), monetary values are valid, state abbreviations are valid US states. Return structured JSON with each field and a confidence score 0-100."
- Use structured output / function calling to enforce the response schema
- Parse response into extraction_data and confidence_scores

7. Save extraction_data and confidence_scores to Document record
8. Update Document status to 'completed'

Error handling:
- If Textract fails: retry once after 5 seconds. If still fails, mark as 'failed' with error message.
- If LLM fails: use raw Textract output without validation, set all confidence scores to 70 (medium).
- Never let the task crash silently — always update the document status.

Create a MOCK MODE for local dev: if AWS_ACCESS_KEY_ID is not set or equals "testing", skip Textract and return hardcoded realistic W2/DL extraction data with high confidence scores. This lets us build the frontend without needing real AWS creds.

---

## Phase 3: Filing Flow UI

### Task 3.1 — Filing Flow Layout & Navigation
Create the filing flow shell at `src/app/file/layout.tsx`.

This layout wraps all filing step pages and provides:
- A progress bar at the top — animated width using Framer Motion, shows current step out of total
- Step labels below the bar (small text, current step highlighted in violet)
- Clean minimal chrome — NO navbar during filing, just the progress indicator
- Exit button (X icon, top-left) that saves draft and navigates to /dashboard
- Framer Motion AnimatePresence for page transitions — slide left when advancing, slide right when going back, with a subtle fade

Update `use-filing-store.ts` with:
- steps: ['w2', 'identity', 'confirm', 'details', 'summary', 'submit']
- currentStep index
- nextStep() and prevStep() actions
- The filing object, documents array, taxProfile, and calculation data
- A createFiling action that POSTs to /api/v1/filings and stores the result

Also implement the filing creation endpoint on the backend:
- POST `/api/v1/filings` — creates a new Filing with status='draft', returns it
- GET `/api/v1/filings` — list current user's filings
- GET `/api/v1/filings/{id}` — get filing detail (verify ownership)
- PATCH `/api/v1/filings/{id}` — update filing_status, filing details

Create the pages as placeholder files for now (just the page.tsx with a heading), we'll implement each one in subsequent tasks:
- `src/app/file/page.tsx` — redirects to /file/w2 and creates a new filing
- `src/app/file/w2/page.tsx`
- `src/app/file/identity/page.tsx`
- `src/app/file/confirm/page.tsx`
- `src/app/file/details/page.tsx`
- `src/app/file/summary/page.tsx`
- `src/app/file/submit/page.tsx`

### Task 3.2 — W2 Capture Page
Implement `src/app/file/w2/page.tsx`.

Use the DocumentCamera component with documentType='w2'.

Flow:
1. User sees full-screen camera interface
2. On capture: show a processing overlay with animated messages cycling every 2 seconds ("Reading your W2...", "Extracting tax data...", "Crunching numbers...", "Almost there...") — use Framer Motion AnimatePresence to fade between messages. Show a pulsing violet gradient orb animation as the AI indicator.
3. Upload the file to POST /api/v1/documents/upload
4. Poll GET /api/v1/documents/{id}/status every 2 seconds
5. On status='completed': show success checkmark animation, then auto-advance to identity step after 1 second
6. On status='failed': show friendly error ("We couldn't read that W2. Let's try again.") with "Retake Photo" button

After successful first W2, show the captured W2 as a small card/thumbnail with:
- Green checkmark overlay
- "W2 from [Employer Name]" text (from extraction data)
- "Add Another W2" button below it

Store document data in useFilingStore.

### Task 3.3 — DL Capture Page
Implement `src/app/file/identity/page.tsx`.

Same pattern as W2 capture but:
- documentType='drivers_license'
- DL-shaped overlay
- Explain why: "We need your ID to verify your identity with the IRS" — shown as a small info banner above the camera
- Processing messages: "Reading your ID...", "Verifying identity...", "Almost done..."
- On success: auto-advance to confirm step

### Task 3.4 — Data Confirmation Page
Implement `src/app/file/confirm/page.tsx`.

Fetch extracted data from all documents in the current filing.

Display in a clean form layout using shadcn Card, Input, Label, Form components:

Section 1 — "Your Information" (from DL):
- Full Name (editable input)
- Street Address (editable)
- City, State, Zip (editable, inline row)
- Date of Birth (editable)

Section 2 — "Your Income" (from W2, repeat for each W2):
- Card header: "W2 from [Employer Name]"
- Employer Name (editable)
- Employer EIN (editable)
- SSN — MASKED display: "XXX-XX-1234", tap to reveal temporarily (3 seconds then re-mask)
- Wages - Box 1 (editable, formatted as currency)
- Federal Tax Withheld - Box 2 (editable, formatted as currency)
- State (editable, dropdown of US states)
- State Wages - Box 16 (editable, formatted as currency)
- State Tax Withheld - Box 17 (editable, formatted as currency)

Each field has a confidence indicator dot:
- Green dot (confidence > 95): high confidence
- Yellow dot (confidence 80-95): "Please verify" — field has a subtle yellow border
- Red dot (confidence < 80): "Needs attention" — field has a red border and is auto-focused

Use Framer Motion for the confidence dot animations (pulse on yellow/red).

Bottom CTA: "Everything Looks Right" shadcn Button — on click, PATCH the document data with any corrections and PUT the tax profile, then advance to details step.

### Task 3.5 — Filing Details Page
Implement `src/app/file/details/page.tsx`.

Filing status selector — show as large, tappable shadcn Cards in a 2x2 grid:
- Single (icon: User)
- Married Filing Jointly (icon: Users)
- Married Filing Separately (icon: UserMinus)
- Head of Household (icon: Home)

Each card shows the status name, a one-line description ("For most unmarried people"), and is selectable (violet border + checkmark when selected). AI pre-selects one based on extracted data (just default to Single for MVP).

Below the selector, show an info Card:
- "Standard Deduction: $15,000" (amount updates based on selected filing status)
- "This is automatically applied and is the best option for most people."

Additional required questions (minimal, as toggle switches using shadcn):
- "Can anyone claim you as a dependent?" — Yes/No
- "Did you have health insurance coverage all year?" — Yes/No

Greyed-out "Dependents" section with "Coming in v1.1" badge.

Big CTA button: "Calculate My Return" — calls POST /api/v1/filings/{id}/calculate, shows loading animation (the pulsing AI orb), on success advance to summary.

### Task 3.6 — Return Summary Page (THE MONEY SCREEN)
Implement `src/app/file/summary/page.tsx`. This is the most important screen — make it BEAUTIFUL.

Fetch calculation results from GET /api/v1/filings/{id}/calculation.

Hero section:
- If REFUND: Big animated number counting up from $0 to the refund amount using Framer Motion (animate the number value over ~2 seconds). Green gradient text. Trigger a confetti animation (build a simple canvas-based confetti effect, no library). Text: "You're getting back"
- If OWED: Calm display, orange/amber text, empathetic copy: "You owe". No celebration. Helpful tone.

Breakdown section — clean Card with rows (NOT a table):
- Each row: label on left, amount on right, subtle divider line
- Gross Income → minus Standard Deduction → equals Taxable Income → Federal Tax Calculated → minus Already Paid (Withheld) → equals Your Refund / Amount Owed
- Use subtle Framer Motion stagger animation — each row fades in sequentially

Charts section (two cards side by side on desktop, stacked on mobile):
- Pie chart (Recharts): "Where Your Federal Taxes Go" — Defense 15%, Healthcare 25%, Social Security 23%, Safety Net Programs 8%, Interest on Debt 8%, Everything Else 21%. Use our violet/purple color palette.
- Bar chart (Recharts): "Your Refund vs Average" — 3 bars: "You" (violet), "State Average" (gray), "National Average" (gray). Use mock averages for now.

AI Insights section — THIS STREAMS IN:
- Card with a sparkle/wand icon and "AI Tax Advisor" header
- Use Vercel AI SDK's useCompletion hook to stream the explanation from a Next.js API route
- Create `src/app/api/insights/route.ts` — calls OpenAI with the tax data context, streams the response
- The text should type out word-by-word like ChatGPT
- Show the pulsing gradient orb while waiting for the stream to start
- Below the explanation, show 1-2 tip cards (e.g., "💡 IRA Contribution — Contributing to a Traditional IRA could save you up to $X next year")

CTAs at bottom:
- Primary: "File My Federal Return — Free" (big gradient button, Framer Motion hover effect)
- Secondary: "Add [State] State Return — $14.99" (outline button)

---

## Phase 4: Tax Engine & AI

### Task 4.1 — Federal Tax Calculator
Implement `services/tax_calculator.py`. This is the core tax engine — it must be 100% correct.

Store the 2025 federal tax bracket data as a constant dict keyed by filing status. Each entry is a list of (upper_bound_cents, rate) tuples. Include brackets for: single, married_joint, married_separate, head_of_household.

Store the 2025 standard deduction amounts as a constant dict keyed by filing status. All values in cents.

Functions:
- `get_standard_deduction(filing_status: str) -> int` — returns deduction in cents
- `calculate_federal_tax(taxable_income_cents: int, filing_status: str) -> int` — progressive bracket calculation, returns tax in cents. Iterate through brackets, calculate tax for the portion of income within each bracket range.
- `calculate_return(filing_id: UUID, db: AsyncSession) -> TaxCalculation`:
  1. Fetch the Filing and its TaxProfile
  2. Get total_wages and total_federal_withheld from TaxProfile
  3. adjusted_gross_income = total_wages
  4. standard_deduction = get_standard_deduction(filing_status)
  5. taxable_income = max(0, adjusted_gross_income - standard_deduction)
  6. federal_tax = calculate_federal_tax(taxable_income, filing_status)
  7. refund_or_owed = total_federal_withheld - federal_tax
  8. Create and save TaxCalculation record
  9. Return it

ALL VALUES IN CENTS. No floats anywhere. Integer arithmetic only.

Implement `routers/tax.py`:
- POST `/api/v1/filings/{id}/calculate` — calls calculate_return, returns the TaxCalculation
- GET `/api/v1/filings/{id}/calculation` — returns existing TaxCalculation for the filing

Write comprehensive tests in `tests/test_tax_calculator.py`:
- Test single filer at each bracket boundary
- Test married filing jointly brackets
- Test zero income → zero tax
- Test income exactly at a bracket boundary
- Test standard deduction reduces taxable income correctly
- Test refund scenario (withheld > tax)
- Test owed scenario (withheld < tax)
- Test all four filing statuses
- Test that results are always integers
- Test negative taxable income floors to zero
- Aim for 100% line coverage on the calculator functions

### Task 4.2 — AI Insights Service + Streaming Endpoint
Implement `services/ai_insights.py`:

`generate_insights_prompt(calculation: TaxCalculation, profile: TaxProfile) -> str`:
- Build a prompt string with all the tax data context
- System instruction: "You are a friendly, clear tax advisor for filefree.tax. Explain this person's tax return in plain English that a 22-year-old would understand. Be encouraging if they're getting a refund. Be empathetic if they owe. Never use jargon. Keep the explanation under 150 words. Then provide 1-2 specific, actionable tips for how they could save on taxes next year. Include dollar amounts where possible."

On the backend, create an endpoint:
- GET `/api/v1/filings/{id}/insights/stream` — streams the AI response using FastAPI's StreamingResponse + OpenAI's streaming API

On the frontend, create:
- `src/app/api/insights/route.ts` — a Next.js API route that proxies to the backend streaming endpoint (or calls OpenAI directly with the Vercel AI SDK)
- This is what the useCompletion hook on the summary page connects to

Also implement a fallback: if OpenAI is down or errors out, generate a basic template insight without AI:
- "You earned [wages] this year. After the standard deduction of [deduction], your taxable income was [taxable]. You owed [tax] in federal taxes, and your employer withheld [withheld]. [You're getting back X / You owe X]."

---

## Phase 5: Submit & Dashboard

### Task 5.1 — Submit Flow
Implement `src/app/file/submit/page.tsx`.

Condensed return summary at top (Card):
- Filing Status, Gross Income, Federal Tax, Refund/Owed — just the key numbers, one line each

E-sign section (Card):
- Header: "Verify Your Identity"
- Explanation: "The IRS needs one of these to verify it's really you"
- Option A: "5-digit IRS PIN" — input field, numeric, 5 digits
- Option B: "Last year's AGI" — input field, currency formatted
- Small text: "Don't have either? You can request an IRS PIN at irs.gov"

Consent section:
- shadcn Checkbox: "Under penalties of perjury, I declare that the information on this return is true, correct, and complete."
- Link: "Read full terms of service"

Submit button:
- Disabled until consent is checked and PIN/AGI is filled
- "Submit to IRS" with gradient background
- On click: POST /api/v1/filings/{id}/submit
- Loading state: "Submitting your return..." with the AI orb animation

On success — celebration screen:
- 🎉 "Your Return Has Been Submitted!"
- "We'll email you when the IRS accepts it (usually 24-48 hours)"
- "Estimated refund date: [~21 days from today]"
- Confetti animation again
- "Go to Dashboard" button

Backend endpoint:
- POST `/api/v1/filings/{id}/submit` — FOR MVP: save all return data, update filing status to 'submitted', create Submission record with mock data. Don't actually transmit to IRS. Return success.
- GET `/api/v1/filings/{id}/submission` — return submission status

**MVP DISCLAIMER**: Show a small banner on the success screen: "Demo Mode — Your return has been saved but not transmitted to the IRS."

### Task 5.2 — Dashboard
Implement `src/app/dashboard/page.tsx`.

Header: "Welcome back, [First Name]" with the date.

Filing status card (main Card, prominent):
- Current filing with status Badge (Draft / Submitted / Accepted / Processing / Refund Sent)
- Horizontal stepper with icons showing the IRS processing steps: Submitted → Accepted → Processing → Refund Sent
- Current step highlighted in violet, future steps in gray
- If accepted: "Estimated refund date: [date]"
- If rejected: red badge, show reason, "Fix & Resubmit" button
- Tax year and filing status shown

Quick actions row:
- "Download Return (PDF)" — generates PDF using @react-pdf/renderer with the tax return data
- "File State Return" CTA if state filing hasn't been done
- "View Full Summary" links back to the summary page

Mini charts section (smaller versions of the summary page charts):
- Refund amount card with the big number
- Pie chart card (compact)

Upsell cards row:
- "Audit Shield — $29/year" card with shield icon, brief copy
- "Get Your Refund Early" card with clock icon, brief copy
- Both have "Learn More" buttons (link to # for now)

---

## Phase 6: Polish & Production Readiness

### Task 6.1 — Loading States & Skeletons
Create skeleton/loading components for every page:
- `src/app/file/loading.tsx` — skeleton for filing flow
- `src/app/dashboard/loading.tsx` — skeleton for dashboard
- Skeleton components for: Card, Form fields, Chart placeholders

Use shadcn Skeleton component as base. Add a subtle shimmer animation.

Ensure every async operation (API calls, file uploads, calculations) shows a visible loading state. Never show a blank screen or frozen UI.

### Task 6.2 — Error Boundaries & Error States
Create `src/app/error.tsx` — global error boundary with:
- Friendly error illustration (build with CSS/SVG, not an image)
- "Something went wrong" message
- "Try Again" button that resets the error boundary
- "Go Home" button

Create specific error states for:
- Camera permission denied
- Network/API errors
- OCR extraction failure
- Tax calculation error

Each has: friendly message, suggested action, retry mechanism. Never show technical error details to the user.

Create `src/app/not-found.tsx` — custom 404 with filefree.tax branding.

### Task 6.3 — Animations & Micro-interactions
Do an animation polish pass across the entire app:

- Page transitions: slide + fade between all filing steps (should already work via AnimatePresence in layout, verify and tune)
- Button interactions: scale down slightly on press, gradient shifts on hover
- Form fields: label floats up on focus with smooth transition
- Number animations: count-up effect on all dollar amounts on summary and dashboard
- Confetti: canvas-based confetti on submit success and on summary page if refund (build custom, ~50 particles, gravity, fade out after 3 seconds)
- Progress bar: smooth spring animation when advancing steps
- Card hover: subtle translateY(-2px) + shadow increase on desktop
- Staggered list animations: rows in the tax breakdown fade in one by one
- The AI insight streaming should have a blinking cursor at the end while streaming

Use Framer Motion for everything. Keep animations fast (200-400ms). Nothing should feel slow or over-animated.

### Task 6.4 — Responsive Design Pass
Go through every single page and test at these widths: 375px (iPhone SE), 390px (iPhone 14/15), 768px (iPad), 1024px (laptop), 1440px (desktop).

Fix:
- Any horizontal overflow or scroll
- Text that gets cut off or wraps awkwardly
- Touch targets smaller than 44x44px on mobile
- Charts that don't resize properly
- Camera component on mobile portrait and landscape
- Forms that are hard to use on mobile (inputs too small, keyboard covers content)
- The filing flow should feel native-app-quality on mobile

### Task 6.5 — PWA Setup
Add Progressive Web App support:
- `public/manifest.json` with filefree.tax name, violet theme color, icons at multiple sizes
- Generate app icons (use a simple "FF" lettermark in violet, create as SVG, export sizes)
- Basic service worker for offline shell (just cache the app shell, not API data)
- Apple-specific meta tags for iOS Add to Home Screen
- Splash screen configuration

When users "Add to Home Screen" on mobile, it should launch fullscreen with the filefree.tax icon and splash screen, feeling like a native app.

### Task 6.6 — SEO & Meta Tags
Add metadata to all pages using Next.js Metadata API:
- Title: "filefree.tax — File Your Taxes for Free in 60 Seconds"
- Description: "Take a photo of your W2 and file your federal taxes for free. AI-powered, instant filing for simple tax returns."
- Open Graph tags with title, description, and OG image
- Twitter Card tags

Create an OG image (1200x630) programmatically using Next.js OG image generation or as a static asset.

Add JSON-LD structured data on the landing page (Organization + WebApplication schema).

Create `src/app/sitemap.ts` and `src/app/robots.ts` using Next.js file conventions.

---

## Phase 7: Testing

### Task 7.1 — Tax Calculator Tests
Make sure `tests/test_tax_calculator.py` has 100% line and branch coverage on the tax calculator module. Add any missing cases:
- Every bracket boundary for every filing status
- Zero income, max reasonable income (e.g., $1M)
- Exactly at each bracket threshold (both sides)
- Standard deduction exceeds income (taxable income = 0)
- Multiple W2s with different amounts
- Verify all outputs are integers (no float contamination)

Run: `pytest tests/test_tax_calculator.py -v --cov=app.services.tax_calculator --cov-report=term-missing`

### Task 7.2 — API Integration Tests
Create `tests/test_api.py` with integration tests:
- Full auth flow: register → login → /me returns user → logout → /me returns 401
- Create filing, verify it's returned in list
- Upload document (mock S3), verify status endpoint works
- Trigger calculation with known inputs, verify output matches expected
- Verify user A cannot access user B's filings (auth isolation)
- Verify rate limiting on auth endpoints

Use pytest fixtures with a test database and test Redis instance.

### Task 7.3 — Frontend Component Tests
Set up Vitest + React Testing Library in the frontend.

Write tests for:
- DocumentCamera: test permission handling states (granted, denied, error)
- Data confirmation form: test field editing, validation, form submission
- Summary page: test that correct amounts render, test refund vs owed display
- Auth forms: test validation (empty fields, invalid email, password mismatch)
- Navigation: test that filing flow steps advance correctly