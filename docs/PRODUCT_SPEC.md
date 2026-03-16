## FileFree UX & Product Specification
**Version**: 4.0 | **Updated**: 2026-03-09
**Company**: Paperwork Labs LLC

This is the UX reference bible for FileFree (a Paperwork Labs product). It defines the design system, component specs, UX guidelines, and animation tokens. For business requirements see PRD.md. For build tasks see TASKS.md.

### Product Vision: Filing → Advisory → Financial Platform

FileFree is NOT just a tax filing tool. The UX must lay groundwork for the full journey:
1. **Filing** (2026): Free, fast, anxiety-free tax prep. Earns trust.
2. **Advisory** (2027): AI tax advisor that helps users optimize year-round. Monetizes trust.
3. **Financial Platform** (2028+): Recommended financial products, embedded in the advisory relationship.

Every screen in the filing flow should subtly build toward the advisory relationship. After filing, the user should feel: "This app understands my finances better than I do. I want it to help me year-round."

### MVP vs Phase 2+ Delineation

**Sprint 1-2 (must ship by April 15)**:
- Landing page with email waitlist
- Camera capture with document overlay (the "wow" moment)
- OCR pipeline with demo endpoint (try-before-signup)
- Animated field cascade on extraction
- /pricing page with free-forever guarantee

**Sprint 3 (must ship by May 31)**:
- Full filing flow with auth
- OCR auto-fill with manual entry fallback
- Tax calculator (100% test coverage)
- Return summary with refund reveal animation
- 1040 PDF generation with submission instructions
- AI insights (static, not streaming)
- Tax receipt viral card
- Mobile-first responsive design
- Dark mode with indigo/violet aesthetic
- Advisory teaser on post-filing screen

**Phase 2+ (cut for MVP speed)**:
- Streaming AI insights (static first)
- E-file via transmitter partner (October 2026)
- State tax calculation (June-September 2026)
- Referral system with tracking
- Email lifecycle / drip campaigns
- Tax Optimization Plan ($29/year) annual purchase
- Financial product referrals
- Admin dashboard
- PWA setup

---

### Refund Plan Screen (Revenue-Critical — The Monetization Moment)

The Refund Plan screen appears immediately after the return summary / refund reveal. This is the highest-intent financial decision moment of the user's year — they just learned their refund amount and are deciding what to do with it. Every recommendation must be genuinely helpful, not salesy.

**Screen layout: `/filing/{id}/refund-plan`**

Header: "Your Refund Plan" with sparkle icon
Subheader: "Here's how to make your $[refund_amount] work harder."

**Section 1: "Where should your refund go?" (IRS Form 8888 integration)**
- Interactive allocation UI showing refund amount as a progress bar
- Drag sliders or type amounts to split refund across up to 3 accounts
- Default: 100% to their existing bank account (no pressure to change)
- Option A: "Put $[suggested] in a 5.5% APY savings account" — partner link to HYSA (Marcus, Wealthfront, Betterment). Shows projected earnings ("Earn $[amount] by next tax season").
- Option B: "Start a Roth IRA with $[suggested]" — partner link. Shows "Your future self will thank you" messaging.
- Option C: "Keep everything in your checking account" — always default, always prominent.
- Affiliate disclosure (small, clear): "FileFree may receive compensation when you open a partner account."
- When user allocates to a partner account, pre-fill IRS Form 8888 with routing/account numbers for e-file or PDF.

**Section 2: "3 things that could save you money next year" (Financial Referrals)**
- Personalized recommendations based on filing data (not generic):
  - W-4 adjustment: "You're overpaying $[amount]/month. Here's how to fix it." (Free, in-app tool)
  - IRA contribution: "Contributing $[amount] by April 15 would save you $[savings] in taxes." (Partner link)
  - HYSA: "Your refund could earn $[amount] in interest this year." (Partner link if not already routed above)
- Each recommendation: icon + title + one-sentence explanation + estimated dollar impact + CTA
- Maximum 3 recommendations (not overwhelming)
- Skip button always visible: "Maybe later" or "Go to my return"

**Section 3: "Peace of mind" (Audit Shield upsell)**
- Small card, not aggressive: "Want audit protection? $19/year covers you if the IRS has questions."
- Single CTA: "Add Audit Shield" or "No thanks"
- Only show if user has not already purchased

**UX rules for this screen:**
- NEVER block the user from proceeding. The default is "keep everything in checking + skip recommendations."
- Recommendations must feel helpful, not transactional. The tone is "smart friend giving genuine advice."
- No countdown timers, no urgency tactics, no dark patterns.
- Affiliate disclosures are visible but not distracting (small text below the recommendation section).
- Track: `refund_plan_viewed`, `refund_routing_selected` (with partner), `recommendation_clicked`, `audit_shield_purchased`

### Tax Optimization Plan ($29/year — Annual Purchase)

Replaces the original monthly AI Advisory subscription. Purchased at filing time as a one-time annual add-on.

**Offer surface:** After the Refund Plan screen (or on the post-filing dashboard).
- "Get your personalized Tax Optimization Plan — $29/year"
- Shows 2-3 specific things the plan would help with based on their data
- Example: "Your W-4 is set wrong. The Tax Optimization Plan includes a W-4 calculator that could put $200/month back in your pocket."

**What's included:**
- W-4 adjustment calculator with paycheck impact preview
- IRA contribution optimizer with tax savings projection
- Year-over-year comparison (when they file next year)
- Quarterly estimated tax reminders (for gig income users)
- Priority support during tax season
- One personalized insight email per month

**Dashboard Advisor Card (for purchasers):**
- Appears on dashboard after purchase
- Header: sparkle icon + "Your Tax Optimization Plan"
- Shows next action item and estimated savings
- Links to W-4 calculator, IRA optimizer, etc.

**For non-purchasers (free tier):**
- Dashboard shows a "Tax Tips" card with one generic monthly tip
- Soft upsell: "Unlock your personalized plan for $29/year"

### Tracking Pixels (Page-Level Components)

**TikTok Pixel:** Install via `next/script` in the root layout. Track: `PageView` (all pages), `CompleteRegistration` (signup), `SubmitForm` (filing completion), `ViewContent` (refund plan screen). Required for TikTok Spark Ads conversion tracking.

**Meta Pixel:** Install via `next/script` in the root layout. Track: `PageView`, `Lead` (signup), `CompleteRegistration` (filing completion), `ViewContent` (refund plan screen). Required for Meta/Instagram ad boost conversion tracking.

Both pixels must respect user consent preferences and be covered by the privacy policy. Implement a simple cookie consent banner (required for GDPR, good practice for CCPA).

**Pricing UX (/pricing page)** — see detailed spec in "/Pricing Page Detailed Specification" section below:
- Three sections: "Free Forever" filing, "E-File Status" (interim), "Tax Optimization Plan $29/yr"
- Honest comparison table vs competitors
- "What's the catch?" FAQ that builds trust
- E-file cost-passthrough explained transparently
- No dark patterns. No hidden fees. No bait-and-switch. This is the anti-TurboTax.

---

### Tax Receipt Viral Card Specification (Growth-Critical)

After filing, offer a shareable "tax receipt" graphic — the tax equivalent of Spotify Wrapped.

**Card content (user opts in to each)**:
- "Filed in [X] minutes" (always shown)
- "Refund: $X,XXX" (opt-in toggle)
- Filing date
- "Filed free with FileFree" footer with logo
- filefree.tax URL

**Visual design**: dark card with gradient border, subtle glow effect, FileFree logo watermark. Should look premium enough that people want to share it.

**Formats**:
- Instagram Story (1080x1920)
- Twitter/X card (1200x675)
- General share (1080x1080)

**Implementation**: Generate server-side using @vercel/og or canvas API. One-tap share or download.

---

### Try-Before-Signup Flow (Growth-Critical)

The biggest trust barrier is asking users to create an account before they see value. Fix: let users try the OCR without signing up.

**Flow:**
1. Landing page CTA: "Snap Your W2 — See It In Action"
2. User uploads or photographs a W2 (no account needed)
3. OCR processes the document; fields cascade in with animation
4. User sees their extracted data (employer name, wages, etc.)
5. Gate: "Create a free account to save your return and calculate your refund"
6. On sign-up, anonymous session data transfers to new account seamlessly

**Implementation:**
- POST `/api/v1/documents/demo-upload` — rate limited (3/day per IP), no persistent storage (process and discard image after extraction)
- Extracted data stored in browser sessionStorage until account creation
- On account creation, POST extracted data to create Filing + TaxProfile

**Why this matters:**
- Reduces friction to zero for first experience
- Creates shareable "wow" moments ("look what this app does!")
- Builds trust through demonstration, not promises
- Natural conversion point with immediate value

---

### Manual Entry Fallback (First-Class, Not Degraded)

If OCR fails or user doesn't have their W2 photo handy, the manual entry path must be equally polished.

**Design:**
- Same form layout as the OCR confirmation screen
- Each field labeled with its W2 box number: "Box 1 — Wages, tips, other compensation"
- Help text explains where to find each value on the physical W2
- Pre-populate with whatever OCR DID extract (partial success is common)
- Visual: small W2 diagram highlighting the relevant box location
- Entry point: "Enter your W2 info manually" link on the camera screen, or automatic redirect on OCR failure

---

### 1040 PDF Template Specification

The app must generate a downloadable IRS Form 1040 PDF using @react-pdf/renderer.

**Requirements:**
- Match official IRS Form 1040 field layout (positions, sizes)
- Correct fonts (IRS forms use Courier for data, variable for labels)
- Include: completed Form 1040 with all computed values
- Cover page: "Your 2025 Federal Tax Return — Prepared by FileFree"
- Instructions page: Step-by-step guide for submitting via IRS Free File or mail
- Footer: "This return was prepared by FileFree (filefree.tax). E-file coming October 2026."

---

### E-File UX Transition (Column Tax SDK — October 2026)

When Column Tax SDK is integrated for interim e-file, the user transitions from FileFree's UI to an embedded third-party SDK. This must feel seamless, not jarring.

**Flow:**
1. User completes full FileFree flow: OCR, confirm data, filing details, calculate, review summary
2. Summary page displays two equally prominent CTAs:
   - **Primary**: "Download Your Return (PDF) — Free" (always available, always prominent)
   - **Secondary**: "E-File Now (~$X, at cost)" with an info icon tooltip
3. Tooltip/expandable text on e-file CTA: "We're going through the rigorous IRS e-file certification process. Until we're certified (target: early 2027), e-file is powered by Column Tax. You pay exactly what we pay — no markup. Once certified, e-file will be free forever."
4. On "E-File Now" click: Column Tax SDK opens in embedded iframe or modal overlay
5. Column Tax UI is white-labeled with FileFree branding (logo, colors) where their SDK allows
6. All user data (name, SSN, income, deductions, calculated tax) pre-filled via Column Tax API — user should NOT have to re-enter anything
7. User reviews one final time in Column's UI, confirms, submits
8. On success: Column SDK closes, FileFree celebration screen appears (confetti, "Your return has been filed!")
9. On failure: show clear error with FileFree-styled messaging, option to retry or download PDF instead

**Design rules:**
- The transition to Column Tax SDK should NOT feel like leaving FileFree. Minimize visual disruption.
- If Column Tax SDK cannot be sufficiently white-labeled, consider a full-page explanation screen before the handoff: "You're about to submit your return through our e-file partner. Everything's pre-filled — just confirm and submit."
- The free PDF download button must NEVER be hidden or de-emphasized. It is always the free path.
- After e-file submission, all status tracking happens in FileFree's dashboard (poll Column Tax for status).

**Post-certification (January 2027+):**
- Remove Column Tax SDK entirely for simple returns (1040, standard deduction)
- Replace with own MeF submission flow — no iframe, no third-party UI
- "E-File — Free" becomes the primary CTA. PDF download becomes secondary.
- Keep Column Tax as fallback for complex returns not yet supported by own transmitter

---

### /Pricing Page Detailed Specification (Trust-Critical)

The /pricing page is one of the most important pages for trust and conversion. It must be crystal clear, honest, and directly address the "Is this really free?" skepticism.

**URL:** `/pricing`
**Linked from:** navigation bar, landing page, footer, FAQ

**Layout — Three sections:**

**Section 1: "Tax Filing — Free Forever"**
- Large heading with checkmark icons for each item
- Federal tax preparation — Free
- State tax preparation (all income-tax states) — Free
- AI-powered W-2 scanning (proprietary OCR) — Free
- Completed 1040 PDF download — Free
- E-file (once IRS certification complete, early 2027) — Free
- All filing statuses, up to 3 W-2s — Free
- Subtext: "No hidden fees. No upsells during filing. No bait-and-switch. We will never charge for tax preparation."

**Section 2: "E-File Status" (temporary, remove after January 2027)**
- Callout card with amber/info styling (not error — informational)
- "We're currently completing IRS e-file certification — a rigorous process that takes several months. Until we're certified:"
- "Download your return (PDF) and mail it — Free"
- "E-file through our certified partner — ~$X (at cost, no markup)"
- "Once certified (target: early 2027), e-file will be free forever."
- This section is honest and turns a limitation into a trust signal

**Section 3: "Tax Optimization Plan — $29/year" (Premium, Optional)**
- Year-round personalized tax optimization
- W-4 withholding optimizer
- IRA/401k contribution calculator
- Year-over-year comparison and suggestions
- Priority support during tax season
- "This is how we make money. Filing is free. Advisory is optional."

**Bottom Section: "What's the Catch?" FAQ**
- "Is FileFree really free?" — "Yes. Tax preparation, PDF download, and (soon) e-file are free forever. We make money when you optionally buy our Tax Optimization Plan ($29/year) or use recommended financial products. Filing is our way of earning your trust."
- "Why do I have to pay for e-file right now?" — "We're going through the IRS e-file certification process. It's rigorous and takes several months. Until then, you can download your return for free, or e-file through our certified partner at cost. We don't mark up the price."
- "Is my data safe?" — "Your data is encrypted with 256-bit encryption. SSNs are processed locally and never sent to AI services. We never sell your data. You can delete your account and all data anytime."
- "How do you make money?" — "Our Tax Optimization Plan ($29/year) and optional financial product recommendations. We never charge for filing."

**Comparison Table:**

| Feature | FileFree | TurboTax Free | FreeTaxUSA | Cash App Taxes |
|---|---|---|---|---|
| Federal Prep | Free | "Free" (upsells) | Free | Free |
| State Prep | Free | $39.99+ | $15.99 | Free |
| W-2 OCR Scan | Yes (AI) | Yes | Limited | No |
| E-File | Free (Jan 2027) | "Free" | Free | Free |
| Speed | ~5 min | 30+ min | 20-40 min | 15-30 min |
| Data Selling | Never | Lawsuit pending | No | Cross-sell |

---

### Breakpoints

Design mobile-first. Every component starts with its mobile layout and adds complexity at `lg` breakpoint. The filing interview flow should look identical on mobile and desktop — one question per screen doesn't need a different layout.

---

### UX Guidelines

These are the rules every screen, component, and interaction must follow. When in doubt, refer back to these.

**Voice & Tone:**
- Speak like a smart, calm friend who happens to know taxes — not like software, not like the IRS, not like a chatbot.
- Use "you" and "your." Never "the taxpayer" or "the user."
- Use contractions. "You're getting $2,400 back" not "You are receiving a refund of $2,400."
- Headings are human questions or statements: "Where did you live in 2024?" not "Primary Residence Information."
- Error messages explain what happened AND what to do: "We couldn't read your W-2. Try uploading a clearer photo, or type the numbers in manually."
- Never blame the user. "That doesn't look like a valid SSN — double-check the last four digits?" not "Invalid SSN entered."
- Celebrate wins. When the user completes a section, acknowledge it briefly: "Income section done — nice work."

**Information Density:**
- One concept per screen in the filing flow. If you're showing more than 3-4 form fields, split the screen.
- Use progressive disclosure everywhere. Show the simple version, let users expand for detail.
- Labels above inputs, never beside them (beside labels break on mobile and reduce scanability).
- Help text below the input in muted text. Only show it for fields that genuinely need explanation.
- Never show all sections of a form at once. Accordion or step-by-step only.

**Loading & Performance Perception:**
- Target: first meaningful paint under 1 second, time-to-interactive under 2 seconds.
- Skeleton screens for any content that takes more than 200ms to load. Match the skeleton shapes to the actual content layout.
- Spinners only for actions that the user explicitly triggered (submit, upload). Never for page loads.
- Optimistic updates for auto-save: mark the field as saved immediately, roll back if the API fails.
- Prefetch the next step's data when the user is 80% through the current step.

**Trust Signals:**
- This is a tax app. Users are entering their SSN, income, and bank details. Trust isn't a nice-to-have — it's existential.
- Show a lock icon + "256-bit encrypted" near sensitive fields (SSN, bank account).
- Display a security badge or trust bar in the footer of the filing flow.
- Show your data handling policy in plain English, accessible from every page (not buried in a legal page): "Your data is encrypted, never sold, and deleted when you ask."
- HTTPS everywhere (obviously), but also show users that it's secure — the green lock matters psychologically.
- When asking for SSN, explain WHY you need it in a help tooltip: "The IRS requires your Social Security Number to identify your tax return."

**Empty States:**
- Every screen that could be empty has a designed empty state with an illustration (or icon + text), a message, and a CTA.
- Dashboard with no returns: "Ready to file? Let's get your taxes done." + Start Filing button.
- Document list with no uploads: "No documents yet. Upload your W-2 or 1099 to get started." + Upload button.
- Prior years with no history: "This is your first year with FileFree. After you file, your returns will show up here."

**Responsiveness Rules:**
- Max content width: 672px (max-w-2xl) for the filing flow. It's a focused, single-column experience. Don't let it stretch across a 27" monitor.
- Max content width: 1280px (max-w-7xl) for the dashboard.
- Sidebar navigation on desktop (lg+), bottom tab bar on mobile.
- Cards stack vertically on mobile, grid on desktop.
- Tables convert to card lists on mobile (never horizontal scroll a table on a phone).

---

### UX Tasks

---

### Task 1.0 — Design System Foundation

Implement the design system specification above as code. This is the first frontend task — nothing else gets built until this is done.

Set up the Tailwind config (`tailwind.config.ts`) with all custom color tokens as CSS variables. Follow the shadcn/ui convention: define colors as HSL values in `globals.css` under `:root` (light) and `.dark` (dark), reference them in the Tailwind config via `hsl(var(--primary))`. This way, toggling dark mode swaps all colors globally.

Install and configure `next-themes` with `attribute="class"` and `defaultTheme="system"`. Create a `ThemeToggle` component (sun/moon icon button with rotation animation) and place it in the top navigation.

Set up Inter via `next/font/google` in the root layout. Configure Tailwind's `fontFamily.sans` to use the loaded font variable.

Create a `lib/utils.ts` file with the `cn()` helper function (clsx + tailwind-merge).

Create a `lib/motion.ts` file that exports animation presets:
- `fadeIn`, `fadeOut` — opacity transitions
- `slideInRight`, `slideInLeft` — for interview step transitions
- `slideInUp` — for modal/drawer entrances
- `scaleIn` — for button press effects
- `countUp` — spring config for number animations
- A `useReducedMotion()` hook that reads `prefers-reduced-motion` media query
- A `<MotionDiv>` wrapper component that respects reduced motion

Initialize shadcn/ui. Run the init command, configure the style (New York theme — it's slightly more refined than the Default theme), set the base color to slate, set the border radius to 0.5rem. Install these shadcn/ui components immediately: button, input, label, card, dialog, sheet, tooltip, popover, dropdown-menu, select, checkbox, radio-group, switch, textarea, separator, badge, skeleton, progress, toast (or swap for sonner), form (wraps react-hook-form), command (cmdk-based, for potential command palette later).

Create a `DESIGN_SYSTEM.md` file in the project root that documents every token value, component variant, and animation preset. This is the reference document for every future UI decision. Include visual examples as comments describing what each token looks like.

Acceptance criteria: A developer can build any screen in the app using only the design tokens, shadcn/ui components, and motion presets without making any aesthetic decisions. Every decision is already made.

---

### Task 1.1 — Component Library Extensions

Build the application-specific components that sit on top of shadcn/ui primitives. These are used throughout the app and need to be rock-solid before building screens.

**FormField component** — Wraps shadcn/ui's form primitives. Includes: label (above), input, helper text (below, muted), error message (below, destructive, with 3px shake animation on appear), optional info tooltip icon next to the label. Handles the `react-hook-form` field registration automatically. Variants: text, email, phone (with formatting), SSN (masked: shows •••-••-1234, with a toggle to reveal), currency (auto-formats with $ and commas as user types), date (with date picker popover), address (with Google Places autocomplete).

**SSNInput component** — Special handling: renders as password-style dots by default, "Show" toggle to reveal, auto-formats with dashes as user types (XXX-XX-XXXX), validates format on blur, shows lock icon to reinforce security. Never logs the value to console. Never includes in analytics events.

**CurrencyDisplay component** — Renders a dollar amount with Framer Motion count-up animation when the value changes. Props: `value`, `size` (sm/md/lg/xl), `color` (auto: green for positive refund, amber for owed), `animate` (boolean). Used for the running refund estimate and the final reveal.

**FileUploadZone component** — Wraps react-dropzone. Shows a dashed border zone with an upload icon and "Drop your document here, or click to browse" text. On drag-over, the border becomes solid primary color and background shifts to accent. Shows file type restrictions below ("PDF, JPG, or PNG • Max 10MB"). On upload, transitions to a progress bar, then to a file preview card with filename, size, and a remove button. Handles multiple files. Error state: "That file type isn't supported — try a PDF or image."

**StepProgress component** — The persistent filing progress indicator. Shows the major phases (About You, Income, Deductions, Credits, Review, File) as a horizontal bar on desktop, collapsible on mobile. Current phase is highlighted with primary color. Completed phases show a check icon and are clickable (navigates back). Upcoming phases are muted. Within the current phase, show a thin progress bar or "Step 3 of 7" text. Animates smoothly when advancing between phases and steps.

**InterviewQuestion component** — The standard wrapper for every filing flow screen. Includes: a heading (h2), optional subheading (body text, muted), the form content (slot), and a bottom action bar with "Back" (ghost button, left) and "Continue" (primary button, right). On mobile, the action bar is sticky at the bottom of the viewport. The "Continue" button shows a loading spinner when the next step is being saved/loaded. Animate the content area (fade + slide) when transitioning between questions.

**InfoTooltip component** — A small (?) icon that opens a popover (desktop) or bottom sheet (mobile) with a plain-English explanation. Props: `term` (the jargon word), `explanation` (simple text). Used next to every tax term in the app. Create a central dictionary of all tax term explanations so they're consistent everywhere.

**StatusTracker component** — Horizontal or vertical stepper for post-filing status. Steps: Submitted → Accepted → Processing → Refund Issued (or Payment Processed). Each step shows a date if completed, a pulsing dot if current, and is grayed out if upcoming. Animates when status changes.

**EmptyState component** — Props: `icon` (Lucide icon), `title`, `description`, `actionLabel`, `onAction`. Renders a centered, padded layout with the icon, text, and a CTA button. Used everywhere something could be empty.

**SecureBadge component** — Small inline component showing a lock icon + "Encrypted & Secure" text. Placed near sensitive form sections (SSN, bank info, document upload).

---

### Task 1.2 — Layout Shell & Navigation

Build the app's outer layout structure that wraps every authenticated page.

**Desktop (lg+):**
- Left sidebar (w-64), collapsible to icon-only (w-16). Contains: FileFree logo at top, nav links (Dashboard, File Taxes, Documents, Settings), theme toggle and user menu at bottom.
- Main content area with a top bar showing: current page title (left), notification bell + user avatar (right).
- Content centered with appropriate max-width per page type.

**Mobile (below lg):**
- No sidebar. Top bar with hamburger menu (opens sidebar as a sheet/drawer from left) + logo centered + user avatar right.
- Bottom tab bar with 4 items: Dashboard (home icon), File (file-text icon), Documents (folder icon), Settings (gear icon). Active tab uses primary color, inactive uses muted. Tabs animate with a subtle scale on tap.
- Bottom tab bar hides when scrolling down (content gets full screen), reappears on scroll up. Smooth transition.

**Filing flow layout:**
- During the filing interview, the sidebar/bottom tabs collapse or hide. The filing flow takes over the full screen with only the StepProgress bar at top and the InterviewQuestion layout. This creates focus and reduces distraction. A small "Save & Exit" link in the top corner lets users escape back to the dashboard.

All layout transitions (sidebar collapse, tab bar hide/show, page transitions) use Framer Motion with the established duration/easing tokens.

---

### Task 1.3 — Landing / Marketing Page

The public-facing page for unauthenticated users. This is the first impression. It must load fast, feel premium, and convey trust.

**Hero Section:**
- Headline: "File Your Taxes. Free. No Tricks." (or equally direct — A/B test this later via PostHog).
- Subheadline: one sentence explaining the value prop. "Smart tax filing that guides you step by step. No hidden fees. No upsells. Just done."
- One primary CTA button: "Start Filing — It's Free." Links to sign-up.
- Background: subtle gradient or abstract geometric pattern (generated with CSS, not an image). Optional: a clean illustration of the product UI (a stylized screenshot or mockup of the filing flow).

**Social Proof Section (populated after launch):**
- Aggregate rating: "Rated 4.8/5 by X,XXX filers."
- 3-4 testimonial cards with user quotes (collected via the in-app feedback widget, Task 1.21).
- Logos of press mentions or notable endorsements (if any).
- Counter: "X,XXX returns filed for free" — this number grows and creates trust through social proof.

**How It Works Section:**
- Three steps with icons and short descriptions: (1) Answer simple questions about your year, (2) We find every deduction you qualify for, (3) File directly with the IRS — for free.
- Steps animate in (stagger fade-in) as user scrolls into view.

**Comparison Section:**
- A simple, honest comparison table: FileFree vs. TurboTax vs. H&R Block vs. IRS Direct File. Columns: Price (federal), Price (state), OCR document scanning, form coverage, mobile experience. Don't trash competitors — let the facts speak. FileFree wins on price and features; competitors win on brand recognition and breadth. Be honest about your current form coverage limitations.

**Trust Section:**
- Security badges / statements: IRS-authorized e-file provider (when applicable), 256-bit encryption, "Your data is never sold."
- If you have user count or filing stats later, show them here.

**FAQ Section:**
- 5-7 most common questions, expandable accordion. "Is FileFree really free?" "What tax situations do you support?" "Is my data safe?" "How long does it take to file?" "What if the IRS rejects my return?" This section doubles as SEO content for long-tail queries.

**Footer:**
- Links: About, Privacy Policy, Terms, Security, Contact/Support, Blog/Guides.
- Keep it minimal.

Performance requirements: Lighthouse score 95+ on all categories. No layout shift. Font preloaded. Hero section renders on first paint. No third-party scripts above the fold.

---

### Task 1.4 — Auth Flow (Sign Up / Sign In)

**Sign Up:**
- Page design: centered card on a clean background. Logo at top, form in center, "Already have an account? Sign in" link below.
- Progressive fields — don't show everything at once. Step 1: email address + "Continue" button. Step 2: create password (with real-time strength indicator: a segmented bar that fills and changes color as the password gets stronger — no "must include uppercase and special character" until they try to submit). Step 3: first name (just first name, not full name — you need it for the welcome screen).
- "Sign up with Google" button above the email field as an alternative. Separated by an "or" divider.
- After successful sign-up, send a verification email (via Mailhog in dev). Show a "Check your email" screen with the email address displayed and a "Resend" link.
- Transition between steps: horizontal slide animation.

**Sign In:**
- Same card layout. Email + password fields visible together (sign-in is a returning action, no need to split steps).
- "Forgot password?" link below the password field. Triggers a password reset email flow.
- "Sign in with Google" button.
- On successful sign-in, redirect to dashboard (or to filing flow if they were mid-filing when they left).

**Magic Link (optional, nice-to-have):**
- Offer "Sign in with email link" as an alternative to password. User enters email, gets a one-time link, clicks it, and they're in. Lower friction for returning users who don't remember their password.

**Session Timeout:**
- After 30 minutes of inactivity, show a modal overlay: "Still there? For security, we'll need you to sign in again if you're inactive much longer." with a "I'm here" button that resets the timer, and an automatic redirect to sign-in after 5 more minutes.
- After re-authentication, return the user to exactly where they were. Store the current route in the session before redirecting.

---

### Task 1.5 — Onboarding & Welcome Flow

Triggered after first sign-up + email verification. This only runs once per user.

**Welcome Screen:**
- Full-screen, centered content. "Hey {firstName}, let's get your taxes done." as the heading.
- Subtext: "Most people finish in under 30 minutes. We'll save your progress — you can leave and come back anytime."
- Big primary button: "Let's Go" — enters the filing flow.
- Secondary link: "I want to look around first" — goes to the dashboard.
- Subtle background animation: a gradient that slowly shifts, or particles that gently float. Nothing distracting — just enough to make the page feel alive.

**Returning User Welcome:**
- When a user returns to the app after 24+ hours and has an in-progress return, show a welcome-back banner at the top of the dashboard (not a full screen — they're a returning user, don't block them): "Welcome back, {firstName}. You were working on your income section — pick up where you left off?" with a "Continue Filing" button.
- The banner dismisses when they click "Continue" or explicitly dismiss it. Don't show it again for that session.

**Year-over-Year Returning User (future consideration, note in tasks):**
- If the user filed last year, offer to pre-populate personal info, address, dependents, employer info from last year: "Want to start with last year's info? You can update anything that changed." This is a major time-saver and retention hook. Design the UX now even if the backend logic comes later.

---

### Task 1.6 — Filing Interview UX

The core product experience. Every screen follows the InterviewQuestion component pattern. Content is specific to each tax topic but the UX structure is consistent.

**Flow Structure (high-level phases):**

Phase 1 — About You: Filing status, personal info (name, SSN, DOB, address), dependents. These are easy confirming questions. Start here to build momentum.

Phase 2 — Income: W-2 employment income, 1099 income (freelance, interest, dividends, etc.), other income. This is where document upload happens.

Phase 3 — Deductions: Standard vs. itemized (help users understand the choice with a plain-English comparison), common deductions (student loan interest, educator expenses, HSA contributions, etc.). Only show deductions that are relevant based on earlier answers.

Phase 4 — Credits: Child tax credit, earned income credit, education credits, etc. Again, only show applicable ones based on their situation.

Phase 5 — Review: Full summary of everything entered. Editable — every section can be clicked to jump back to that question.

Phase 6 — File: Final confirmation, e-signature, submission.

**Interview Screen UX Rules:**

Every question screen follows this pattern:
1. Human-readable heading ("Did you earn any income from freelance or self-employment work?")
2. Optional subtext explaining why this matters or what counts
3. Form content (usually yes/no, a few fields, or a document upload)
4. Back / Continue buttons

Conditional logic must be invisible to the user. If they answer "No" to freelance income, the 1099-NEC section never appears. They should feel like the app was custom-built for their situation. Never show greyed-out or "not applicable" sections — just skip them.

For yes/no questions, use large clickable cards (not small radio buttons). Card shows an icon, the option text, and highlights with primary border + background when selected. Selecting a card auto-advances to the next question after a 300ms delay (gives visual feedback before transitioning).

For sections with multiple items (e.g., multiple W-2s, multiple dependents), use an "add another" pattern: show the first item's form, then after saving it, show a card summarizing what they entered with an "Add Another W-2" button below. Each added item is a card with edit/delete actions.

**Auto-Save:**
- Debounce at 500ms after last field change. Save via react-query mutation.
- Show a small "Saved ✓" text near the progress bar that fades in when saved, fades out after 2 seconds.
- If save fails, show "Couldn't save — retrying..." and retry with exponential backoff (3 attempts). If all retries fail, show a toast: "Having trouble saving. Check your connection." with a manual retry button.
- On page load, always fetch the latest saved state from the server. Never rely solely on local state.

**Running Refund Estimate:**
- After Phase 2 (Income) is complete, show a persistent but non-intrusive estimate. On desktop: a floating pill in the top-right corner of the content area showing "Estimated refund: $X,XXX" (or "Estimated owed: $X,XXX"). On mobile: a collapsible bar below the StepProgress.
- As the user completes deductions and credits, animate the number up or down using the CurrencyDisplay component. This creates a reward loop — "that deduction just saved me $300" is a dopamine hit that keeps them going.
- The estimate should be labeled clearly as an estimate: "This may change as you add more info."
- Color: green tint when refund, amber tint when owed.

---

### Task 1.7 — Document Upload & OCR UX

This is one of the strongest "wow" moments in the product. A user drops a W-2, and their form fills itself in. Make this feel magical.

**Upload Screen:**
- The FileUploadZone component takes center stage. Large drop zone, friendly copy.
- Below the drop zone, show a visual list of document types with icons: W-2, 1099-NEC, 1099-INT, 1099-DIV, etc. User can click one to set the expected type before uploading, or let the system auto-detect from OCR.
- On mobile, offer a camera button prominently: "Take a Photo" with a camera icon. Opens the device camera. Provide tips in a tooltip: "Lay the document flat on a dark surface. Make sure all four corners are visible."

**Upload Progress:**
- After dropping a file: show a file card with the filename, a progress bar for the upload, and a "Processing..." label.
- When OCR is processing (takes a few seconds), show an engaging skeleton state or a subtle animation — maybe a scanning-line effect across a document thumbnail. Label: "Reading your document..."
- Do NOT show a blank spinner. Show something that communicates "we're actively working on this."

**OCR Results Review:**
- When OCR completes, show the extracted data in a form layout matching the document type (e.g., W-2 fields: employer name, EIN, wages, federal tax withheld, etc.).
- Next to each field, show a confidence indicator. High confidence (>95%): field is pre-filled, small green check icon. Medium confidence (80-95%): field is pre-filled but highlighted with an amber border and a tooltip: "Double-check this — we weren't 100% sure." Low confidence (<80%): field is left empty with a prompt: "We couldn't read this clearly — mind typing it in?"
- If the OCR extracted a document thumbnail, show it alongside the form so the user can visually cross-reference.
- The auto-fill moment: when the OCR review screen appears, animate the fields filling in one by one with a quick stagger (50ms between each field). This cascade effect is the "magic" moment — don't skip it.

**Error Handling:**
- If OCR completely fails: "We couldn't read this document. It might be blurry or in an unsupported format. You can try a clearer photo, or enter the information manually." Show a "Enter Manually" button that opens the standard form fields for that document type.
- If the file is too large: "That file is over 10MB. Try a lower-resolution photo or a compressed PDF."
- If the file type is wrong: "That looks like a .docx file — we need a PDF, JPG, or PNG."

---

### Task 1.8 — Review & Submission Flow

The most nerve-wracking part for users. They're about to submit something to the IRS. The UX must feel thorough, reassuring, and double-checked.

**Review Screen:**
- Full summary organized by phase. Each phase is a collapsible card: "About You" (shows name, filing status, dependents), "Income" (shows each income source and amount), "Deductions" (shows standard or itemized, total), "Credits" (shows each credit claimed).
- Every section has an "Edit" button that jumps directly to that part of the interview.
- Highlight any items that might need attention with an amber info callout: "You entered $0 for state taxes withheld — is that correct?" These smart alerts catch common mistakes before filing.
- At the bottom of the review: the final tax number, large, using the CurrencyDisplay component. "Your federal refund: $3,247" or "You owe: $412."
- A toggle or link: "View as Tax Form" that shows a read-only render of the actual 1040 (and supporting schedules) they're about to file. Some users want to see the real form. It should look like the actual IRS form, rendered in HTML/CSS, not a downloadable PDF (PDF download comes after filing).

**E-Signature:**
- Legal disclosure text in plain English (not legalese) with the IRS-required jargon clearly labeled: "By signing, you're declaring under penalties of perjury that everything here is true and correct to the best of your knowledge."
- Two signature methods: (1) Type your full legal name into a field — it renders in a handwriting-style font as a visual "signature." (2) Draw your signature with touch/mouse on a canvas pad. Either is legally valid for e-file.
- A PIN field for the IRS e-file PIN (or option to use prior year AGI as identity verification). Explain what this is in an InfoTooltip.
- Checkbox: "I consent to e-file my federal return with the IRS."

**Submission:**
- The "File My Return" button is prominent, primary, full-width on mobile. It does NOT auto-submit — user must explicitly click.
- On click: button enters loading state ("Filing...") with a progress animation. Call the API.
- If the API confirms the e-file was submitted: transition to a success screen (see Task 1.9).
- If the submission fails: show a clear error. "The IRS rejected your submission because [reason]." with guidance on how to fix it and a "Fix & Refile" button. Common rejection reasons should have human-readable explanations mapped to IRS error codes.

---

### Task 1.9 — Refund / Owed Reveal & Post-Filing

The emotional climax. Treat this like a product launch moment.

**Refund Reveal Screen:**
- Full-screen takeover. Clean background (slight gradient or radial glow).
- Brief suspense: a 1-second delay with a subtle "calculating" shimmer, then the number animates in.
- Large CurrencyDisplay centered on screen with count-up animation from $0 to the final amount (1.5 seconds, spring easing).
- If refund: trigger canvas-confetti from the bottom of the screen. Not overwhelming — 50-80 particles, gold and indigo colors, fades after 2 seconds. Message: "You're getting $X,XXX back!" in a celebratory but classy tone.
- If owed: no confetti, calm tone. The number appears in amber. Message: "You owe $X,XXX — and that's totally manageable." Immediately show payment options below (direct pay, payment plan, etc.) so they don't spiral.
- Below the number: "Here's how we got there" expandable breakdown. Show a simple visual: income (bar), minus deductions (bar), minus credits (bar), equals tax owed/refund. Use a horizontal stacked bar or a simple list with amounts.

**Post-Filing Actions (below the reveal or on scroll):**
- "Download Your Return" — PDF download of the completed 1040 and schedules.
- "View Filing Confirmation" — shows the e-file confirmation number, timestamp, and status.
- "Set Up Direct Deposit" (if they haven't already) — for receiving the refund.
- "Go to Dashboard" — takes them to the status tracker.

**Share / Referral Moment:**
- This is the peak happiness moment — the user just got good news (refund) or closure (filed successfully). Surface the referral CTA here, but keep it light and genuine: "Know someone who's still paying for tax software? Share FileFree." with a one-tap copy of their referral link, or share buttons for text/WhatsApp/social. Don't make this a popup or modal — it's an inline section below the post-filing actions.

---

### Task 1.10 — Dashboard & Return Status

The home base for authenticated users. Clean, card-based, informative.

**Primary Card — Current Filing Status:**
- If no return started: large CTA card. "Ready to file your 2024 taxes?" + "Start Filing" button.
- If return in progress: shows phase progress. "You're 60% done — pick up where you left off." + "Continue Filing" button.
- If return filed: StatusTracker component showing current IRS status (Submitted → Accepted → Processing → Refund Issued). Show last updated timestamp. If refund issued, show the amount and expected deposit date.

**Secondary Cards:**
- "Your Refund" — estimated or confirmed refund amount with the CurrencyDisplay. If refund has been issued, show "Deposited on [date]" with a green check.
- "Documents" — count of uploaded documents with a link to the document manager.
- "Prior Year Returns" — list of prior filings (just year + refund amount + status) with download links.
- "Tax Tips" (future) — seasonal tax tips or reminders (estimated tax payments, document checklists, etc.).

**Referral Card (persistent):**
- Small card: "You've referred {count} friends. Share your link: filefree.tax/ref/{code}" with a copy button. If count is 0: "Know someone who needs to file? Share FileFree and help them save."

**Empty Dashboard (new user, no filing started):**
- Don't show empty cards. Show the welcome CTA card prominently and a brief "What to expect" section: "Grab your W-2, give us 20 minutes, and we'll handle the rest."

All cards use subtle entrance animations (stagger fade-in-up) on page load. Status tracker polls for updates every 5 minutes (via react-query's refetchInterval) and animates when status changes.

---

### Task 1.11 — Micro-Interactions & Motion System

This task is about implementing the global motion rules, not individual component animations (those are part of each component's task).

Configure Framer Motion's `<AnimatePresence>` at the top level of the app layout for page transition support.

Create a reusable `<PageTransition>` wrapper that animates content in/out. The filing interview uses slide-left (forward) / slide-right (backward). Other pages use a simple fade.

Define and export all animation variants from `lib/motion.ts` as named Framer Motion variant objects so they're consistent everywhere:

- `fadeVariants` — opacity 0 → 1 on enter, 1 → 0 on exit
- `slideVariants` — combines x-axis slide with opacity, direction controlled by a custom prop
- `scaleVariants` — slight scale up (0.95 → 1) + opacity for modals and cards
- `staggerContainer` — parent variant that staggers children by 50ms
- `staggerChild` — child variant for use inside stagger containers
- `countUpVariants` — spring-based number animation config

Button hover: scale to 1.02, transition 100ms. Button active/press: scale to 0.98, transition 50ms. Both via Framer Motion's `whileHover` and `whileTap`.

Form field focus: border-color transition to primary (via CSS transition, 150ms), subtle box-shadow glow (0 0 0 3px with primary color at 10% opacity).

Toast enter: slide in from top, spring animation. Toast exit: fade + slide up, 200ms.

Skeleton pulse: CSS animation (not Framer Motion — it runs independently and doesn't need JS).

Number changes (CurrencyDisplay, progress percentages): spring animation with `stiffness: 300, damping: 30`, updating via `useSpring` or `useMotionValue`.

All of this must respect `prefers-reduced-motion`. When reduced motion is active: no position animations, no scale effects, no springs — opacity fades only at duration 0 (instant). The app should still be fully functional and visually clear without any motion.

---

### Task 1.12 — Error & Edge Case UX

Design and implement error handling as a first-class UX concern, not an afterthought.

**Validation Errors:**
- Inline, below the field. Red text, text-sm. Field border turns destructive color. Field shakes gently on error appear (x-axis, 3px amplitude, 300ms, ease-out — using Framer Motion).
- Errors appear on blur or on submit, never while the user is still typing (except for real-time feedback like password strength).
- When a form has errors on submit, scroll to the first error field smoothly and focus it.

**API Errors:**
- Never show raw error messages or status codes to users.
- Network errors: sonner toast — "Connection problem. We'll retry automatically." with a manual "Retry Now" button if auto-retry exhausts.
- Server errors (5xx): sonner toast — "Something went wrong on our end. Try again in a moment." Log the error to your monitoring service (Sentry or similar).
- Validation errors from API (4xx): map to specific field errors and show inline.
- Rate limiting (429): "You're moving fast! Give us a second and try again." (Don't tell them it's rate limiting.)

**Offline Detection:**
- Use `navigator.onLine` + `online`/`offline` events.
- When offline: show a non-dismissible banner at the top of the screen. "You're offline. Your work is safe — we'll sync when you're back." Amber background, not red.
- Queue any save operations. When back online, flush the queue and show "Back online — everything's synced." banner briefly.

**Session Expiry:**
- Modal overlay (not redirect): "Your session expired. Sign in to pick up where you left off." Email pre-filled, just needs password.
- After re-auth, close modal and user is exactly where they were. Zero data loss.

**Multi-Tab Warning:**
- If the user has the filing flow open in two tabs (detected via BroadcastChannel API), show a warning: "You have FileFree open in another tab. To avoid conflicts, please use one tab at a time." Don't hard-block — just warn.

**Unsaved Changes Warning:**
- If the user navigates away from a form with unsaved changes (via browser back button or clicking a nav link), intercept with a modal: "You have unsaved changes. Save them before leaving?" with Save / Discard / Cancel buttons. Use Next.js router events to detect navigation.

---

### Task 1.13 — Mobile UX

Mobile is not a responsive afterthought — it's a primary platform. Many users will file their taxes on their phone. Every screen must be designed and tested on a 375px-wide viewport.

**Touch Targets:**
- Minimum 44x44px for all interactive elements. Audit every button, link, icon button, and checkbox.
- Form inputs: minimum height 48px. Padding inside inputs should be generous (py-3).

**Mobile-Specific Patterns:**
- All modals render as `vaul` bottom sheet drawers on viewports below `lg`. No centered dialogs on phones.
- InfoTooltips: tap opens a bottom sheet (not a hover popover — there's no hover on mobile).
- Interview flow: "Continue" button is in a sticky bottom bar (with a subtle top border and blurred background), always accessible without scrolling. "Back" button is in the top-left of the screen.
- Swipe-to-go-back gesture in the filing flow (swipe right from left edge to go to previous question). Implement with Framer Motion's `drag` prop with directional lock.

**Camera Integration:**
- On document upload screens, detect mobile device and show a prominent "Take a Photo" button (camera icon) above the standard drop zone.
- Use `<input type="file" accept="image/*" capture="environment">` for rear camera access.
- After photo capture, show a preview with crop/rotate tools (or at minimum a retake option) before uploading.

**Keyboard Handling:**
- When a form input is focused and the virtual keyboard opens, ensure the input is scrolled into view and not hidden behind the keyboard.
- Use `inputMode` attributes: "numeric" for SSN, EIN, zip code, currency fields (brings up the number pad). "email" for email fields. "tel" for phone fields.
- Auto-advance focus to the next field when the current field's max length is reached (e.g., SSN segments).

**Performance:**
- Test on low-end devices (use Chrome DevTools' throttling: "Slow 3G" + "4x CPU slowdown").
- Skeleton loading is especially critical on mobile — users on slow connections need visual feedback immediately.
- Lazy load below-the-fold content and non-critical components.

---

### Task 1.14 — Accessibility

WCAG 2.1 AA compliance is the minimum. Tax filing must be accessible to everyone — this is also a legal concern for a tax product.

**Keyboard Navigation:**
- Every interactive element is reachable via Tab. Tab order follows visual order.
- Focus rings are visible and styled to match the design system (2px ring with `ring-ring` color, offset by 2px). Never `outline: none` without a visible replacement.
- Modal focus trapping: when a modal/drawer is open, Tab cycles within it. Escape closes it. Focus returns to the trigger element on close. (shadcn/ui handles this via Radix, but verify it.)
- Filing interview: Enter key submits the current step (triggers "Continue"). This is essential for keyboard-only users.

**Screen Readers:**
- All form fields have associated `<label>` elements (shadcn/ui's form component handles this).
- All images and icons have appropriate `alt` text. Decorative icons use `aria-hidden="true"`.
- Status changes (auto-save confirmation, filing status updates, validation errors appearing) are announced via `aria-live="polite"` regions.
- The StepProgress component announces the current step to screen readers: "Step 3 of 7: Income, W-2 Information."
- Page transitions announce the new page title.
- The CurrencyDisplay count-up animation should have a final `aria-label` with the actual value — screen readers shouldn't read every intermediate number.

**Color & Contrast:**
- All text meets 4.5:1 contrast ratio against its background (AA). Large text (18px+ or 14px+ bold) meets 3:1.
- Verify for both light and dark mode using a contrast checker.
- Don't rely on color alone to convey information. The refund/owed indicator uses color AND text AND an icon.
- Error states use red color AND text description AND icon.

**Motion:**
- Respect `prefers-reduced-motion` globally (see Task 1.11).
- No content is only accessible via animation. If something animates in, it's also present in the DOM for screen readers immediately.

**Typography:**
- All font sizes in rem (never px for text). If the user increases their browser's default font size, the app scales gracefully.
- Test at 200% browser zoom — the layout should remain usable.
- Line length for reading content should max out at ~70 characters (this is naturally handled by the max-w-2xl constraint in the filing flow).

**Forms:**
- Required fields are indicated by a "(required)" label suffix (not just an asterisk — asterisks are ambiguous).
- Error messages are associated with their fields via `aria-describedby`.
- Group related fields (e.g., address components) with `<fieldset>` and `<legend>`.
- Auto-complete attributes set correctly: `autocomplete="given-name"`, `autocomplete="family-name"`, `autocomplete="email"`, etc. This helps password managers and autofill.

**Testing:**
- Test with VoiceOver (macOS/iOS), NVDA (Windows) at minimum.
- Run axe-core automated checks in CI via `jest-axe` or `@axe-core/react`.
- Include accessibility testing in the PR review checklist.

---

### Task 1.15 — Trust & Security UX

Building visible trust is as important as actual security for a tax product. Users need to feel safe entering their most sensitive data.

**Visible Security Indicators:**
- Lock icon in the browser bar (HTTPS — handled by infrastructure, but don't break it with mixed content).
- SecureBadge component appears near: SSN input, bank account input, document upload zone, and the e-signature section.
- Footer of every page in the filing flow: "Your data is encrypted in transit and at rest. We never sell your information." with a link to the privacy policy.

**Data Handling Transparency:**
- Settings page includes a "Your Data" section: shows what data FileFree stores, with an option to download all their data (JSON/PDF) and a "Delete My Account & Data" button (with confirmation modal explaining what happens: return data is deleted, filed returns remain on IRS record).
- After filing season, proactively notify users: "Your 2024 return is securely stored. You can download or delete your data anytime."

**SSN Handling:**
- SSN is masked by default everywhere it appears (•••-••-1234). Reveal toggle shows it temporarily (auto-hides after 10 seconds).
- SSN is never logged to analytics, never in URLs, never in console logs.
- On the review screen, SSN shows as masked with a "Verify" button that reveals it temporarily.

**Session Security:**
- Inactivity timeout (30 min) with the modal warning described in Task 1.4.
- Re-authentication required before: viewing full SSN, modifying bank account info, or submitting the return.
- "Sign out of all devices" option in settings.

**Phishing Protection:**
- On the dashboard, include a small note: "FileFree will never ask for your password via email or text." This is a trust signal and a genuine protection.

---

### Task 1.16 — Product Analytics Instrumentation

This is the tracking code embedded in the frontend. It's invisible to users. The data flows to PostHog (hosted at `app.posthog.com` or self-hosted at `analytics.filefree.tax`), where you view dashboards, funnels, session replays, and run experiments. This is not an admin panel — it's a product intelligence layer.

**Setup:**
- Install `posthog-js` and `posthog-react`. Initialize in the root layout with your project API key. Wrap the app in `<PostHogProvider>`.
- Create a `lib/analytics.ts` file that exports a `trackEvent(name: string, properties?: Record<string, unknown>)` wrapper. Every component imports this — never call `posthog.capture()` directly. This abstraction lets you swap analytics providers without touching every file.
- Create a PII filter: before any event is sent, strip out fields matching known PII patterns (SSN, email, full name, address, bank account). This is a safety net. Even if a developer accidentally includes PII in event properties, it gets caught.

**Events to Track:**

Filing funnel (the most critical data — this tells you where you're losing people):
- `signup_started` — user lands on sign-up page
- `signup_completed` — account created successfully
- `email_verified` — clicked verification link
- `filing_started` — entered the filing flow for the first time
- `filing_step_completed` — with properties: `phase`, `step_name`, `step_index`, `time_on_step_seconds`, `direction` (forward/backward)
- `filing_step_skipped` — conditional skip (user said "no" to a question that skipped a section)
- `filing_phase_completed` — with property: `phase_name`
- `filing_review_reached` — they made it to the review screen
- `filing_submitted` — return submitted to IRS
- `filing_accepted` — IRS accepted the return
- `filing_rejected` — IRS rejected, with property: `rejection_code`

Document upload:
- `document_upload_started` — with `document_type`, `file_type`, `file_size_bytes`
- `document_upload_completed` — with `duration_seconds`
- `ocr_completed` — with `document_type`, `fields_extracted`, `avg_confidence`, `low_confidence_field_count`
- `ocr_field_corrected` — user changed an OCR-filled field, with `field_name` (not the value!)
- `ocr_failed` — with `error_type`
- `manual_entry_chosen` — user skipped OCR and entered data by hand

Engagement:
- `session_started` — with `returning_user` boolean, `days_since_last_visit`
- `filing_resumed` — returned to an in-progress filing
- `filing_abandoned` — left mid-flow without completing (detect via session end without submission)
- `refund_estimate_viewed` — tapped/expanded the running estimate
- `document_downloaded` — downloaded their completed return PDF
- `referral_link_shared` — clicked the share/referral CTA
- `referral_signup` — someone signed up via a referral link, with `referrer_id`
- `dark_mode_toggled` — with `new_theme` (useful for knowing adoption)

Growth and Revenue:
- `referral_link_copied` — with `source` (post-filing, dashboard, settings)
- `state_filing_upsell_shown` — (when applicable)
- `state_filing_purchased` — (when applicable)
- `landing_page_cta_clicked` — with `cta_location` (hero, comparison, footer)
- `blog_article_viewed` — with `article_slug`, `referral_source`
- `testimonial_submitted` — with `rating` (1-5)

Errors:
- `client_error` — with `error_message`, `component`, `stack_trace` (truncated)
- `api_error` — with `endpoint`, `status_code`, `error_type`
- `validation_error` — with `field_name`, `validation_rule` (not the invalid value)
- `offline_detected` / `online_restored`

Performance:
- `page_load` — with `page_name`, `load_time_ms`, `time_to_interactive_ms`
- `step_transition` — with `from_step`, `to_step`, `transition_time_ms`

**PostHog Dashboards to Create:**

Acquisition Funnel: landing page visit → signup started → signup completed → email verified → filing started. Shows conversion rate at each step and overall. Filter by date range, traffic source (UTM params), and referral vs organic.

Filing Completion Funnel: filing started → each phase completed → review reached → submitted → accepted. This is the money dashboard. If 60% of people start filing but only 30% submit, you have a problem in the middle. Drill into which phase/step has the biggest drop.

OCR Performance: upload volume by document type, average confidence scores, correction rate (how often users change OCR values), failure rate. If correction rate is high for a specific field, your OCR model needs tuning for that field.

Referral Dashboard: referral links shared, signups via referral, conversion rate from referral signup to completed filing, top referrers. This tells you if the referral system is working and who your power advocates are.

Revenue Dashboard (when applicable): state filing conversions, audit protection conversions, ARPU, revenue by cohort. Tie back to acquisition source — which channels produce users who pay for add-ons?

Error Dashboard: error events grouped by type and screen. Spike detection — if errors jump 3x from the prior day, something broke.

Session Replay: enable session replay for users who triggered an error event or abandoned the filing flow. Watch what happened. This is the most underrated debugging tool — you'll find UX problems in 10 minutes of watching that you'd never catch from metrics alone.

**Feature Flags:**
- Set up PostHog feature flags from day one. Use them for: A/B testing landing page headlines, rolling out new interview questions to a percentage of users, enabling/disabling experimental features (magic link auth, new deduction types), gating paid features (state filing). Create a `useFeatureFlag(flag: string)` hook that returns a boolean. Gate features in the UI with this hook.

**A/B Testing Framework:**
- PostHog's built-in experimentation handles this. Start with these tests once you have traffic: landing page headline variants, sign-up flow (progressive vs. all-at-once), filing flow question ordering (does starting with easy questions improve completion?), refund estimate visibility (show early vs. show late — which drives more completions?), referral CTA placement and copy.

---

### Task 1.17 — Admin Dashboard (Internal Operations)

This is your command center — a protected area of the app (either a `/admin` route behind role-based auth, or a separate subdomain like `admin.filefree.tax`) where you manage operations, debug user issues, and monitor system health. This is NOT the product analytics layer (that's PostHog) — this is operational tooling.

**Access Control:**
- Admin routes are protected by a role check. Your user model should have a `role` field (default: `user`, elevated: `admin`). Admin middleware rejects non-admin users with a 403. In production, only your account has admin access. Keep the admin user list hardcoded or in an environment variable — don't build a full RBAC system yet.

**Admin Dashboard Home:**
- Real-time stats cards at the top: total users, active filings (in progress), completed filings (submitted), accepted by IRS, rejected by IRS, total refund dollars processed. Each card shows the number + change from prior period (day/week).
- A line chart showing filings over time (daily for last 30 days). Use recharts.
- A "System Health" indicator: green/yellow/red based on API response times, error rates, and IRS submission queue status. Green means everything is normal. Yellow means degraded (error rate >1% or avg response time >500ms). Red means critical (error rate >5% or IRS submissions failing).
- Revenue widget (when applicable): total state filing revenue, audit protection revenue, monthly trend.

**User Management:**
- Searchable user list. Search by email, name, or user ID.
- User detail view: shows their account info (email, sign-up date, last login), filing status (which phase they're in, last active step, percent complete), documents uploaded (count and types, NOT the actual documents unless absolutely needed for debugging), referral info (who referred them, who they've referred), and a timeline of key events (signed up, started filing, uploaded W-2, submitted, etc.).
- Ability to: reset a user's password (sends reset email), impersonate a user (view the app as they see it — essential for debugging "it doesn't work" support requests), disable an account, delete an account and all data (for GDPR/privacy requests).
- User impersonation must be logged and is a sensitive action. Show a bright banner at the top when impersonating: "You are viewing as user@email.com" with an "Exit Impersonation" button.

**Filing Queue:**
- Table of all filings in submission state. Columns: user email, filing status (queued, submitted to IRS, accepted, rejected), submission timestamp, IRS response timestamp, rejection reason (if any).
- Filter by status. Sort by timestamp.
- Ability to manually retry a failed submission.
- Ability to view the generated tax return XML/data for a filing (for debugging IRS rejections).

**Document & OCR Monitor:**
- Table of recent document uploads. Columns: user (anonymized ID or email), document type, upload time, OCR status (pending, completed, failed), confidence score, corrections made.
- Filter by OCR status to find failures. Drill into a specific upload to see the extracted data vs. user-corrected data (this is your training data for improving OCR).

**Referral Monitor:**
- Table of referral activity: referrer, referred user, signup date, filing completed (yes/no). Top referrers leaderboard. Total signups via referral vs. organic vs. paid.

**Error Log:**
- Aggregated view of recent errors from the API. Group by error type, show count and trend (increasing/decreasing).
- Link out to your logging service (if using one) or show recent error details inline.
- This is your first alert when something is broken. Check it daily.

**Email Management:**
- List of recently sent emails: type (verification, filing confirmation, status update, abandonment nudge), recipient (masked email), status (sent, delivered, bounced, opened), timestamp.
- Ability to resend a verification email for a specific user.
- Preview of each email template (rendered via react-email).

**Support Queue:**
- Feed of recent support requests submitted via the contact form (Task 1.21). Shows subject, user email, timestamp, and status (open/responded/resolved). Click to view full message and respond directly.

**Feature Flags (mirror of PostHog):**
- Quick view of active feature flags and their status (on/off, percentage rollout). Links to PostHog for full management. Having this visible in your admin dashboard keeps you aware of what's currently enabled without switching to another tool.

**Design Notes:**
- The admin dashboard doesn't need to be beautiful — it needs to be functional and fast. Use the same shadcn/ui components as the main app but with a denser layout (smaller text, tighter spacing, more data per screen). This is a power-user tool.
- Use `@tanstack/react-table` for all admin tables — it handles sorting, filtering, pagination, and column resizing.
- Dark mode should work here too (you'll be staring at this late at night during filing season).

---

### Task 1.18 — Email Lifecycle System

Email is your primary re-engagement channel. Users who start filing and don't finish need a nudge. Users who filed need to come back next year. This is critical for retention and growth.

**Email Infrastructure:**
- Use `react-email` to build email templates as React components. They use the same design tokens (colors, fonts) as the app for brand consistency.
- Use `resend` for delivery. Set up a verified sending domain: `notifications@filefree.tax`.
- All emails include: FileFree logo, a clear subject line, the email body, an unsubscribe link (legally required and respectful), and a footer with your physical address (CAN-SPAM compliance).

**Transactional Emails (triggered by user actions):**

Welcome email: sent immediately after signup. Subject: "Welcome to FileFree — let's get your taxes done." Body: brief welcome, link to start filing, and a reminder of what they'll need (W-2, etc.).

Email verification: sent on signup. Subject: "Verify your email." Body: verification link with 24-hour expiry. Keep it short.

Filing confirmation: sent when return is submitted to IRS. Subject: "Your tax return has been filed! 🎉" Body: confirmation number, what to expect next (IRS acceptance typically 24-48 hours), link to check status in the app.

IRS acceptance notification: sent when IRS accepts. Subject: "The IRS accepted your return." Body: refund amount (if applicable), estimated deposit date, link to dashboard.

IRS rejection notification: sent when IRS rejects. Subject: "Action needed: your return needs a correction." Body: plain-English explanation of the rejection reason, link to fix it in the app. Don't be alarming — rejections are common and usually easy to fix.

Password reset: standard. Subject: "Reset your password." Body: reset link, 1-hour expiry, "If you didn't request this, ignore this email."

Referral notification: sent when someone signs up via your referral link. Subject: "Someone you referred just joined FileFree!" Body: "{Name} signed up using your link. You've referred {count} people so far."

**Lifecycle Emails (triggered by time/behavior):**

Abandonment nudge #1: sent 24 hours after a user starts filing but doesn't finish. Subject: "You're almost there — pick up where you left off." Body: shows which phase they're in and estimated time remaining. One clear CTA: "Continue Filing." Tone: encouraging, not pushy.

Abandonment nudge #2: sent 72 hours after starting if still not completed. Subject: "Your tax return is waiting for you." Body: slightly different angle — emphasize the refund they might be leaving on the table (if income data suggests a refund). CTA: "Finish & Get Your Refund."

Abandonment nudge #3 (final): sent 7 days after starting. Subject: "Need help finishing your taxes?" Body: offer help — link to support/FAQ, mention the filing deadline, acknowledge that taxes are stressful. This is the last automated nudge. Don't spam.

Tax deadline reminder: sent to all users who haven't filed 2 weeks before the April deadline, and again 3 days before. Subject: "Tax deadline is in X days." Body: if they started a return, link to continue. If they haven't started, link to start. Urgency is legitimate here — use it.

Next year kickoff: sent in late January when W-2s start arriving. Subject: "Tax season is here — FileFree is ready when you are." Body: welcome them back, mention that their info from last year is saved, CTA to start their new return. This is the retention email — the one that brings them back year after year.

Annual receipt: sent after filing. Subject: "Your 2024 tax filing summary." Body: summary of what they filed, refund/owed amount, link to download their return. This is a record-keeping email that also reinforces trust.

**Email Quality Rules:**
- Every email is mobile-responsive. Test in Gmail, Apple Mail, and Outlook (the big three).
- Plain-text version of every email (for accessibility and spam filter compliance).
- Subject lines under 50 characters when possible.
- One CTA per email. Don't confuse the reader with multiple actions.
- Unsubscribe must work instantly. When someone unsubscribes from lifecycle emails, they still get transactional emails (verification, filing confirmation) — those are legally exempt.

**Tracking:**
- Track email opens and clicks via Resend's built-in analytics.
- Feed open/click events into PostHog to see which emails drive re-engagement and which are ignored.
- Track unsubscribe rate. If any email has an unsubscribe rate above 1%, rewrite it — you're annoying people.

---

### Task 1.19 — Referral & Growth Mechanics

A tax app grows primarily through word of mouth — "I used this free thing and it actually worked." Build lightweight growth loops into the product from day one.

**Referral System:**

Every user gets a unique referral link: `filefree.tax/ref/{code}`. The code is a short, readable string (not a UUID). Generate it on account creation.

The referral link is accessible from: the post-filing success screen (Task 1.9 — this is the peak happiness moment), the dashboard (small card: "Know someone who needs to file? Share FileFree."), and the settings page.

When a referred user signs up and completes their filing, both the referrer and the referred user get a benefit. Since FileFree is free, the benefit isn't a discount — it needs to be something else. Options to consider: priority support, early access to new features, a "FileFree Champion" badge on their profile (gamification), or if you ever add paid features (state filing, audit protection), a free upgrade. For launch, a simple "Thanks for spreading the word" acknowledgment + a counter showing how many people they've referred is sufficient. The social proof of "I've helped 5 friends file for free" is motivating.

Track referral chain: who referred whom, when, and whether the referred user completed filing. This data goes to PostHog and is visible in the admin dashboard.

**SEO & Organic Search:**

Create a `/blog` or `/guides` section with tax education content. This is your long-term organic growth channel. Write (or generate and heavily edit) articles targeting common search queries: "how to file taxes for free," "what is a W-2," "standard deduction vs itemized 2025," "how to find your AGI from last year," "first time filing taxes guide."

Each article should: be genuinely helpful (not thin SEO bait), link to the product naturally ("Ready to file? Start with FileFree"), have proper meta tags and Open Graph images for social sharing, and be structured with headers and FAQ schema for featured snippets.

Technical SEO foundations: generate a sitemap.xml via Next.js, add structured data (Organization, FAQProduct, FAQ) to key pages, ensure all pages have unique meta titles and descriptions, implement canonical URLs, and make sure the site is fast (see performance requirements in Task 1.3).

**Social Proof:**

After a user files successfully, prompt them (gently, optionally) to leave a rating or testimonial. "How was your experience? A quick rating helps others find FileFree." Star rating (1-5) + optional text. Don't gate this — ask everyone, not just happy users.

Display aggregate rating on the landing page: "Rated 4.8/5 by X filers." Display select testimonials (with user permission) on the landing page.

If you accumulate enough positive sentiment, submit to Product Hunt, Hacker News (Show HN), and relevant subreddits (r/personalfinance, r/tax). Timing matters — do this when the product is polished, ideally in early February when people are starting to think about taxes.

**Viral Content & Distribution:**

Create shareable "tax receipt" graphics. After filing, offer users an option to generate a visual card: "I filed my taxes in {X} minutes for free with @FileFree" with their (non-sensitive) stats — filing time, refund amount (if they opt in). These are designed for social sharing (Instagram story format, Twitter card format). This is the tax equivalent of Spotify Wrapped — low effort to create, high viral potential.

**Partnerships (future, note for later):**

Partner with financial literacy nonprofits, VITA (Volunteer Income Tax Assistance) programs, or community organizations. Offer FileFree as a tool they can recommend. This drives volume and is aligned with the "free tax filing" mission.

Partner with payroll providers (Gusto, ADP) to offer FileFree as a suggested filing tool when employees download their W-2s. This is a longer-term play but has massive distribution potential.

---

### Task 1.20 — Monitoring, Alerting & Operational Readiness

Tax season is concentrated — 80% of your annual traffic hits in a 10-week window (late January through mid-April). If the system goes down during this window, people miss deadlines and you lose all credibility. Operational readiness isn't optional.

**Application Monitoring:**
- Integrate Sentry (`@sentry/nextjs`) for frontend error tracking. Capture unhandled exceptions, rejected promises, and component error boundaries. Set up source maps so stack traces point to your actual code.
- Configure Sentry alerts: notify you (email + Slack/Discord webhook) when error rate exceeds a threshold (e.g., >10 errors in 5 minutes for a new error, or >50 total errors in 15 minutes).
- API monitoring: log response times and error rates per endpoint. If average response time exceeds 500ms or error rate exceeds 1%, trigger an alert.

**Uptime Monitoring:**
- Use an external uptime monitor (BetterStack, Pingdom, or UptimeRobot's free tier) to check the app every 60 seconds from multiple regions. If the site is down for 2+ minutes, you get notified instantly.
- Create a public status page (status.filefree.tax) so users can check if there's a known issue. BetterStack provides this built-in.

**Performance Monitoring:**
- Track Core Web Vitals (LCP, FID, CLS) via Next.js's built-in reporting or Vercel Analytics (if deployed on Vercel). Set performance budgets: LCP < 2.5s, FID < 100ms, CLS < 0.1.
- Run Lighthouse CI in your deployment pipeline. Fail the build if performance score drops below 90.

**Database Monitoring:**
- Track connection pool usage, query execution time, and slow queries. If using Supabase/Neon, use their built-in dashboards. Set alerts for: connection pool >80% utilized, any query taking >1 second, disk usage >80%.

**IRS Submission Queue:**
- This is mission-critical. If submissions to the IRS fail silently, people think they filed but didn't. Monitor the submission queue constantly during filing season.
- Dashboard widget: show queue depth (submissions waiting), processing rate, success rate, and failure rate. Alert immediately on any failure.
- Implement a dead letter queue for failed submissions. Admin can inspect and manually retry.
- Nightly reconciliation job: compare your submitted count with your accepted/rejected count. If they don't add up, something is stuck.

**Incident Response:**
- Write a simple incident response runbook (a markdown doc): (1) Identify — what's broken, what's the impact. (2) Communicate — post to status page. (3) Mitigate — fix or roll back. (4) Postmortem — write up what happened and how to prevent it.
- Keep a deployment log (even just a markdown file in the repo): what was deployed, when, by whom, and what changed. When something breaks, this is the first thing you check.

**Load Testing (pre-season):**
- Before filing season, run load tests simulating peak traffic. Use k6 or Artillery. Simulate: 100 concurrent users going through the filing flow, 50 simultaneous document uploads with OCR processing, and 20 concurrent submissions. Identify bottlenecks and fix them before real users hit them.
- Test your auto-scaling (if applicable) by ramping from 0 to peak load over 5 minutes.

**Backups:**
- Database: automated daily backups with point-in-time recovery. Test restore at least once before filing season.
- Document storage: ensure uploaded documents are in durable storage (GCP Cloud Storage with versioning enabled).
- User data export: ensure the admin "export user data" function works and is tested, for both user requests and your own disaster recovery.

---

### Task 1.21 — Feedback & Support System

You're a solo builder — you can't staff a support team. Design the support system to be self-serve first, with a lightweight escape hatch to you for real issues.

**In-App Help:**
- The InfoTooltip system (Task 1.1) handles contextual help for tax terms.
- Build a searchable FAQ / Help Center page (`/help`). Cover the top 20 questions you expect: "Is FileFree really free?", "How do I know my data is safe?", "What if the IRS rejects my return?", "How long until I get my refund?", "Can I file a state return?", "What forms does FileFree support?", etc.
- Use a simple search bar at the top that filters articles in real-time. Structure articles with clear headings and short paragraphs.
- Link to relevant help articles from the filing flow contextually. For example, on the e-signature screen, link to "What is the IRS e-file PIN?"

**Contact / Support Form:**
- A simple form on the `/help` page (or `/contact`): email (pre-filled if logged in), subject dropdown (Filing Issue, Technical Problem, Account Help, Feedback, Other), description textarea.
- On submit, this creates an email to your support inbox (support@filefree.tax). Use Resend to send the notification.
- Auto-reply to the user: "We got your message. We'll get back to you within 24 hours." Set this expectation honestly and meet it.
- In the admin dashboard, show a feed of recent support requests so you can triage without leaving your tooling.

**In-App Feedback Widget:**
- On the post-filing success screen and in the settings page, include a small feedback prompt: "How was your experience?" with a 1-5 star rating and an optional comment box.
- Feedback data flows to the admin dashboard, not to PostHog (this is qualitative, not behavioral).
- If someone rates 1-2 stars, auto-show the contact form: "Sorry to hear that. Can you tell us what went wrong? We'll try to fix it."
- If someone rates 4-5 stars, show: "Glad it went well! Would you mind sharing a testimonial?" (optional text box). With permission, these testimonials feed the landing page social proof section.

**Chatbot (future, note for later):**
- A simple AI chatbot that can answer FAQ questions and guide users to the right help article. Not for tax advice — just product support. Only build this if support volume exceeds what you can handle solo. Until then, the searchable FAQ + contact form is sufficient.

---

## PART 3: BUILD ORDER & PROJECT MANAGEMENT

---

### UX Task Priority & Build Sequence

For a solo builder, sequence matters. Each task builds on the ones before it. This is the recommended order — follow it unless you have a strong reason to deviate.

**Foundation (build first, before any screens):**
1. Task 1.0 — Design System Foundation
2. Task 1.1 — Component Library Extensions
3. Task 1.11 — Micro-Interactions & Motion System
4. Task 1.2 — Layout Shell & Navigation

**Core User Flow (the product):**
5. Task 1.4 — Auth Flow
6. Task 1.5 — Onboarding & Welcome Flow
7. Task 1.6 — Filing Interview UX
8. Task 1.7 — Document Upload & OCR UX
9. Task 1.8 — Review & Submission Flow
10. Task 1.9 — Refund / Owed Reveal & Post-Filing
11. Task 1.10 — Dashboard & Return Status

**Polish & Production Readiness:**
12. Task 1.12 — Error & Edge Case UX
13. Task 1.13 — Mobile UX (audit everything built so far)
14. Task 1.14 — Accessibility (audit everything built so far)
15. Task 1.15 — Trust & Security UX

**Growth & Operations:**
16. Task 1.16 — Product Analytics Instrumentation
17. Task 1.17 — Admin Dashboard
18. Task 1.18 — Email Lifecycle System
19. Task 1.20 — Monitoring, Alerting & Operational Readiness
20. Task 1.3 — Landing / Marketing Page (yes, build this late — nail the product first)
21. Task 1.19 — Referral & Growth Mechanics
22. Task 1.21 — Feedback & Support System

---

### How to Use This Document in Cursor

This file is designed to be your AI coding partner's context. When you start a task:

1. Open this file in your project root as `SPEC.md` (or `PRODUCT_SPEC.md`).
2. When starting a new task, tell Claude/Cursor: "I'm working on Task 1.X. Read SPEC.md for full context."
3. The strategic sections (Part 1) give the AI context about WHY you're building something — this leads to better code decisions.
4. The UX task descriptions give enough detail that the AI can implement without ambiguity.
5. The design system spec means the AI will use the right tokens, components, and patterns from the start.

For each task, create a branch: `feat/task-1.X-short-description`. Complete it, test it, merge it, move to the next one.

---

### Version History

- v1.0 (March 2026) — Initial complete specification. Covers strategy, UX, design system, and 22 implementation tasks.