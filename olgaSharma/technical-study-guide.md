# Technical Aptitude Study Guide

Olga Klinger | OpenAI Account Director Interview

This guide walks through three companies and shows exactly how LLMs, prompt engineering, and fine-tuning apply to each. Practice explaining these out loud until you can cover all three concepts for a given company in under five minutes.

---

## Quick Reference: The Hierarchy

Before diving in, remember the progression. Start with prompt engineering (free, fast). If that's not enough, add RAG (your own documents as context). If you still need more specialization, fine-tune. This hierarchy matters because it shows the interviewer you think about cost discipline and customer ROI, not just throwing the most expensive solution at every problem.

---

## Company 1: Uber

### The Business

Uber operates a global ride-sharing and delivery marketplace. They handle millions of real-time transactions, massive customer support volume, and complex operational logistics across dozens of countries.

### LLM Application

**Customer support automation.** Uber handles tens of millions of support tickets per year. Most are repetitive: "where's my driver," "I was charged incorrectly," "my food was cold." An LLM can read the ticket, understand the issue, pull up the relevant order data, and either resolve it automatically or draft a response for a human agent to review.

How to explain it to the interviewer:

"Uber's support volume is enormous, and most tickets follow predictable patterns. An LLM like GPT-5 mini can read a ticket, classify the issue type, pull in the order details through a tool call, and generate a resolution. For straightforward cases like refund requests under a certain threshold, it resolves automatically. For more complex ones, it drafts a response for a human agent, cutting their handling time in half. The model processes language. The business rules around refund thresholds and escalation stay deterministic."

### Prompt Engineering Application

**Localization and tone adaptation.** Uber operates in 70+ countries. Support responses need to match local communication norms. A rider in Tokyo expects a different tone than a rider in Miami.

"Before fine-tuning, I'd start with prompt engineering. You write prompts that specify tone, formality level, and cultural context. Something like: 'Respond to this rider's complaint. Use formal, apologetic language appropriate for a Japanese market. Keep the response under 80 words. Include one concrete next step.' That level of instruction gets you 80% of the way there at zero additional cost. If the customer finds that prompts alone aren't producing consistent enough results across all 70 markets, then we talk about fine-tuning."

### Fine-Tuning Application

**Fraud detection in driver-rider disputes.** Uber deals with a high volume of disputes: riders claiming they were charged for trips they didn't take, drivers claiming riders damaged their vehicles. Adjudicating these requires understanding Uber-specific patterns like trip GPS data, photo evidence, historical dispute behavior, and Uber's internal policies.

"Fine-tuning makes sense here because Uber's dispute patterns are unique to Uber. No general-purpose model understands their specific fraud signals, policy thresholds, or escalation rules out of the box. You'd fine-tune GPT-4.1 on thousands of labeled historical disputes: here's the evidence, here's the outcome, here's why. The fine-tuned model then classifies new disputes with Uber-specific accuracy and recommends resolutions consistent with their actual policies. It's more expensive than prompt engineering, but the consistency at scale justifies it."

**Revenue angle:** "Support automation alone could drive significant token consumption. Millions of tickets per month, each one processed by the model. Add fine-tuned fraud adjudication running on every dispute, and you're looking at substantial consumption revenue that grows with Uber's transaction volume."

---

## Company 2: Spotify

### The Business

Spotify serves 600M+ users with personalized music and podcast recommendations. Their product is built on understanding user taste and surfacing the right content at the right moment.

### LLM Application

**Podcast summarization and discovery.** Spotify hosts millions of podcast episodes. Users don't have time to listen to a 90-minute episode to find out if it's relevant. An LLM can listen (via Whisper transcription), summarize the key points, and generate searchable metadata that makes podcasts discoverable the way songs already are.

"Spotify's podcast catalog is massive, but unlike music, podcasts are hard to browse. You can't skim a podcast the way you skim a playlist. An LLM solves this by transcribing episodes with Whisper, then summarizing the key topics, guest names, and takeaways. Users get a three-sentence summary before they commit to listening. Spotify gets better search and recommendation signals. More content gets discovered, which means more listening hours, which means more ad revenue."

### Prompt Engineering Application

**Playlist naming and description generation.** Spotify auto-generates playlists like Discover Weekly, but the names and descriptions are often generic. Prompt engineering can make them feel personal and contextual.

"Instead of 'Your Daily Mix 3,' the prompt could generate something like 'Tuesday morning deep focus: ambient electronica and lo-fi beats you've been gravitating toward this month.' The prompt would include the user's recent listening patterns, the time of day, and the playlist's genre distribution. You'd instruct the model: 'Generate a playlist title under 10 words and a description under 25 words. Reference specific genres or moods from the user's data. Sound warm and personal, not algorithmic.' That's pure prompt engineering. No fine-tuning needed."

### Fine-Tuning Application

**Content moderation for user-generated playlists and podcast content.** Spotify needs to flag harmful content across hundreds of languages and cultural contexts. General moderation models don't understand Spotify-specific policies around music lyrics, podcast discussions, or playlist naming conventions.

"Spotify's content policies are nuanced. A lyric that's acceptable in a hip-hop playlist might violate policy if it appears as a user-generated playlist title targeting minors. That distinction requires Spotify-specific training data. You'd fine-tune GPT-4.1 mini on labeled examples of policy violations and non-violations drawn from Spotify's actual moderation decisions. The fine-tuned model applies Spotify's specific standards consistently at the scale they need, which is hundreds of millions of pieces of content."

**Revenue angle:** "Podcast summarization alone could process millions of episodes. Every new episode uploaded gets transcribed and summarized. That's ongoing consumption revenue that scales directly with Spotify's content catalog. Add playlist generation and content moderation, and you have three use cases driving daily token usage."

---

## Company 3: Airbnb

### The Business

Airbnb connects travelers with hosts in 220+ countries. Their product depends on trust, accurate listing descriptions, responsive customer service, and matching guests to the right properties.

### LLM Application

**Listing optimization for hosts.** Most Airbnb hosts are individuals, not professional property managers. Their listing descriptions are often incomplete, poorly written, or missing key details that travelers care about. An LLM can analyze a host's photos, existing description, and comparable high-performing listings in the same area, then generate an optimized description that highlights the right selling points.

"Airbnb's revenue scales with bookings. Better listings get more bookings. Most hosts don't know how to write a compelling listing description. An LLM can take a host's raw inputs (photos, amenities checklist, location) and generate a professional, SEO-optimized description that highlights what travelers in that market actually care about. A beach house in Bali gets different emphasis than a studio apartment in Manhattan. The model adapts based on the market data. More bookings per listing means more revenue for Airbnb."

### Prompt Engineering Application

**Customer support response drafting for complex disputes.** Airbnb's support team handles sensitive situations: a guest finds a listing that doesn't match the photos, a host discovers property damage, a cancellation dispute during a holiday. These require nuanced, empathetic communication.

"You'd engineer prompts that include the dispute details, the customer's history and loyalty tier, Airbnb's resolution policies, and tone guidelines. The prompt might say: 'Draft a response to a guest who arrived at a property that didn't match the listing photos. The guest is a Superguest with 12 prior stays. Tone: empathetic and solution-oriented. Offer rebooking assistance and a credit within the $X-$Y range per our policy for this severity. Do not apologize on behalf of the host.' That level of specificity in the prompt gets you a response that's accurate, on-policy, and emotionally appropriate. No fine-tuning required."

### Fine-Tuning Application

**Trust and safety: detecting fraudulent listings.** Airbnb needs to identify fake listings before guests book them. Fraudulent listings often have subtle signals: stock photos, pricing patterns inconsistent with the neighborhood, descriptions that reuse boilerplate language across multiple listings, newly created accounts with unusually polished profiles.

"This is a fine-tuning use case because Airbnb's fraud signals are proprietary. They've built up years of data on which listings turned out to be fraudulent and why. A general model doesn't know that a listing in rural France priced at $45/night with professional photography and a newly created host account is a red flag. Fine-tuning GPT-4.1 on Airbnb's labeled dataset of confirmed fraudulent and legitimate listings creates a model that catches these patterns at scale. It runs on every new listing submitted, every day."

**Revenue angle:** "Listing optimization could run across Airbnb's entire catalog of 7M+ listings. Support response drafting processes millions of tickets. Fraud detection screens every new listing. Three use cases, each with high volume, each generating sustained consumption revenue."

---

## How to Use This in the Interview

You won't be asked to present all three companies. The interviewer will likely ask you to pick one, or they'll name one. Here's your approach:

1. **Start with the LLM use case.** Show you understand what the technology does and why it matters for the business.
2. **Layer in prompt engineering.** Show you understand the cheapest, fastest path to value. This demonstrates cost discipline.
3. **End with fine-tuning.** Show you know when to escalate to a more specialized (and more expensive) approach, and why.
4. **Close with the revenue angle.** Tie it back to consumption revenue. Every use case you described generates tokens, and more adoption means more revenue for OpenAI.

The pattern is always the same: business problem, technical solution, cost-smart progression, revenue implication. Practice that structure and you can apply it to any company they throw at you.

---

## Model Quick Reference

Have these in your head so you can reference them naturally:

| Model | Best For | Price (input/output per 1M tokens) |
|-------|----------|-------------------------------------|
| GPT-5.4 | Most capable, latest release | $2.50 / $15 |
| GPT-5 | Reasoning, complex tasks | $1.25 / $10 |
| GPT-5 mini | High-volume, cost-efficient | $0.25 / $2 |
| GPT-5 nano | Simplest tasks, lowest cost | $0.05 / - |
| GPT-4.1 | Fine-tuning available, 1M context | $2 / $8 |
| GPT-4.1 mini | Fine-tuning available, cost-efficient | Lower |

Key point: **Fine-tuning is available on GPT-4.1 and GPT-4.1 mini, not on GPT-5 models yet.** If the interviewer asks about fine-tuning, always reference 4.1.

---

## Five-Minute Drill

Set a timer. Pick one company. Talk through all three concepts (LLM, prompt engineering, fine-tuning) with a real use case for each. Close with the revenue angle. If you can do it in under five minutes for each company, you're ready.

Do this drill at least three times before the interview, once per company. Say it out loud. Record yourself on your phone if it helps. The goal is fluency, not memorization.
