# Loom Video Script + Interview Prep

Target length: 7-9 minutes. Camera on, screen-sharing the PDF.

## Before You Hit Record

- Open the PDF in Chrome/Preview so it's ready to screen share
- Have this script on your phone or a second screen (not visible on the recording)
- Good lighting on your face, clean background
- Test your mic
- Take a breath. You know this material. You lived it at Meta.

---

## SECTION 1: Opening (0:00 - 1:00)

[START SCREEN SHARE - show the PDF, page 1 visible]

Hi, I'm Olga Klinger, and I chose to focus on Discord for this exercise.

I chose Discord because it's a company I actually know. At Meta Reality Labs, I led the strategic platform partnership with Discord. I shaped product strategy, drove developer integrations at scale, and spent real time inside their ecosystem understanding how it works. So when I think about where AI creates value for Discord, I'm not guessing. I've seen their infrastructure, their priorities, and their gaps up close.

I approached this the way I'd approach a real account plan: what does Discord actually need, and how does OpenAI's full product suite map to that?

Let me walk you through what I came up with.

---

## SECTION 2: The Problem (1:00 - 2:30)

[SCROLL TO "The Problem: Knowledge Dies in the Scroll"]

So starting with the problem.

Discord's biggest strength is real-time, low-friction conversation. But that same strength becomes a liability at scale. If you've ever been in a large Discord server, a crypto project, an open-source community, a brand's fan server, you know the experience. You leave for a weekend and come back to four thousand unread messages. Most people just mute the channel. And muted channels are dead channels.

Members ask the same questions over and over. Moderators burn out repeating themselves. And for Discord's business, this creates a real ceiling on enterprise adoption. Organizations evaluating Discord against Slack and Teams consistently point to the missing knowledge layer as a dealbreaker.

[PAUSE - let this land]

But what really stood out to me is the voice angle. Voice is Discord's biggest differentiator. It's what makes Discord, Discord. But right now, if something important gets said in a voice channel, it's just... gone. There's no record, no way to search it, no way to reference it later. That's a massive missed opportunity, and it's something AI can solve.

---

## SECTION 3: The Solution - Four Capabilities (2:30 - 5:00)

[SCROLL TO "What Discord Should Build"]

So what should Discord build? I'm proposing a Community Intelligence Engine powered by OpenAI. Four capabilities.

[POINT TO Conversation Catch-Up on screen]

First, Conversation Catch-Up. This is the wedge product. It's what you launch first because it's low risk and immediately valuable. Imagine opening a channel and seeing a one-paragraph brief of what happened while you were away, personalized to your role. GPT-5 mini handles the routine daily digests at minimal cost, and GPT-5 steps in for complex multi-day threads that need deeper analysis. Server admins would turn this on in a heartbeat.

[PAUSE briefly]

[POINT TO Voice Intelligence]

Second, Voice Intelligence. This is where Whisper and the Realtime API change things. Whisper handles transcription of recorded voice sessions, and the Realtime API opens up live captioning and even real-time translation for multilingual communities. GPT-5 then turns those transcripts into searchable summaries with key decisions highlighted. Discord becomes the only platform where voice conversations are as discoverable as text. No competitor can touch this.

[PAUSE briefly]

[POINT TO Smart Q&A]

Third, Smart Q&A. Every large server has the same problem. Someone asks "how do I set up X?" and a moderator has to answer it for the fiftieth time. With OpenAI's Embeddings API and retrieval-augmented generation, or RAG, the system searches past conversations and pulls the answer automatically. Comparable deployments show forty to sixty percent reductions in repeat questions. Moderators love this because it gives them their time back.

[POINT TO Community Health Insights]

And fourth, Community Health Insights. Instead of clicking through analytics dashboards, an admin just asks their server in plain language, "what topics drove engagement this week?" or "which channels need attention?" and gets a clear, structured answer back. No charts to interpret, just answers.

---

## SECTION 4: Technical Reasoning (5:00 - 6:30)

[SCROLL TO page 2 - "How the Solution Works Technically"]

Now, I'm not an engineer, but I think it's important to reason through how this would actually work.

[POINT TO the data flow diagram]

The core architecture principle is simple: models suggest, the system executes. The AI doesn't make decisions about permissions or routing or compliance. It does what it's good at, language understanding and synthesis, and then hands off to reliable infrastructure for everything else.

What excites me about this deal from an account perspective is the product breadth. This isn't a single API integration. It touches seven distinct OpenAI products: GPT-5 for complex analysis, GPT-5 mini for high-volume filtering, Whisper and the Realtime API for voice, Embeddings for semantic search, the Moderation API for safety, and Fine-tuning for building community-specific models.

That's a platform partnership, not a point solution.

[PAUSE - let this land]

And from a revenue standpoint, it's a consumption deal. Every channel summary, every voice transcription, every search query, every moderation check generates API volume. The more Discord's users engage with these features, the more API calls flow through.

---

## SECTION 5: Risks (6:30 - 7:30)

[POINT TO the risk table]

I don't think an AI pitch is credible without an honest risk assessment, so let me touch on the key ones.

Hallucination. The system uses a retrieval-only approach, meaning the model only works with actual server content and never generates from general knowledge. That, combined with confidence scoring and human review before anything gets posted, keeps this risk manageable.

Adoption. You don't launch all four features at once. You start with the easiest win, catch-up summaries, prove the value with Discord's top one thousand highest-value servers, and then expand through Nitro tiers. Land and expand.

And cost at scale. At two hundred million monthly active users, you need smart model tiering. GPT-5 mini handles the high-volume routine work like message classification and daily digests at a fraction of the cost. You reserve GPT-5 for the complex analysis. That's how you keep the economics viable at scale.

---

## SECTION 6: Close (7:30 - 8:30)

[SCROLL TO "The Opportunity"]

So to close out.

Bottom line, this is a seven-product, multi-million dollar deal that grows as Discord grows. The consumption model means our incentives are perfectly aligned.

Discord doesn't need to build their own models. They need an intelligence partner, and OpenAI is the only company that covers text, voice, safety, and structured reasoning from a single platform.

[PAUSE - look at the camera]

This is exactly the kind of deal I want to work on. A digital-native company I already know, with massive scale, clear multi-product AI use cases, and a consumption model where OpenAI's revenue grows alongside Discord's engagement. That's the kind of partnership worth building.

Thank you for taking the time to review this. I'm happy to dive deeper into any of these areas.

[STOP RECORDING]

---
---

# OPENAI PRODUCT GLOSSARY

Know these cold. You reference all seven in the proposal and the video. If they ask follow-ups, you should be able to explain each in one or two sentences.

## The Seven Products in Your Proposal

**GPT-5** (the reasoning model family)
OpenAI's flagship reasoning model, released August 2025. Handles text and image inputs with built-in chain-of-thought reasoning. Best for complex tasks: long summarization, nuanced analysis, multi-step reasoning. $1.25 per million input tokens, $10 per million output tokens. 400K context window. The newest model in this family is **GPT-5.4**, released March 5, 2026, with a 1M context window, native computer-use capabilities, and the highest reasoning scores to date ($2.50/$15 per MTok). In your proposal, GPT-5 handles the complex work: multi-day thread summaries, voice transcript analysis, and community health insights.

**GPT-5 mini**
A faster, cheaper version of GPT-5 tuned for speed and cost efficiency. $0.25 per million input tokens, $2 per million output tokens. 400K context window. About 5x cheaper than GPT-5 on a per-token basis. Ideal for high-volume, well-defined tasks like message classification, filtering, and routine daily summaries. There's also a **GPT-5 nano** ($0.05/MTok input) for the absolute cheapest, simplest tasks. In your proposal, GPT-5 mini is the workhorse that keeps costs viable at Discord's scale. This is your cost discipline story: you don't route every message through the expensive model.

**Whisper / Audio API**
OpenAI's speech-to-text system. Transcribes audio in 50+ languages. Supports files up to 25 MB (mp3, mp4, wav, etc.). The original model is called `whisper-1`, and OpenAI has since added newer transcription variants (`gpt-4o-transcribe`) with higher accuracy and speaker identification (diarization via `gpt-4o-transcribe-diarize`). In your proposal, Whisper handles recorded voice channel transcription.

**Realtime API**
A separate product from Whisper. Enables low-latency, live speech-to-speech interactions. The latest model is `gpt-realtime-1.5` (best voice model available), with a cost-efficient `gpt-realtime-mini` variant. Supports WebRTC (browser), WebSocket (server apps), and even SIP for phone systems. In your proposal, this powers live captioning and real-time translation in voice channels. The key distinction from Whisper: Whisper processes recorded audio after the fact, the Realtime API handles live, streaming audio. They're complementary, not interchangeable.

**Embeddings API**
Converts text into numerical vectors (lists of numbers) that capture meaning. Two models available: `text-embedding-3-small` (cheaper, faster) and `text-embedding-3-large` (more accurate). These vectors get stored in a vector database. When someone asks a question, the system converts their question into a vector, finds the closest past conversations by meaning, and feeds those into GPT-5 to generate an answer. This is how RAG works in your proposal.

**Moderation API**
Now called `omni-moderation-latest`. Classifies both text AND images for harmful content: hate speech, violence, self-harm, sexual content, etc. Returns category scores between 0 and 1. The upgrade from the old text-only moderation model to omni-moderation means it can catch harmful images too, not just text. In your proposal, this runs on all messages as a safety layer. It's free, which makes it easy to run at scale without worrying about cost.

**Fine-tuning API**
Lets you train a custom version of a model on your own data. Currently available for **GPT-4.1** and **GPT-4.1 mini** (not yet supported on GPT-5 models). Supports supervised fine-tuning, direct preference optimization (DPO), and even vision fine-tuning. You can get strong results from as few as a few dozen examples. In your proposal, Discord would fine-tune GPT-4.1 mini to understand community-specific norms, slang, relevance signals, and moderation tone for individual servers. As fine-tuning support expands to GPT-5 models in the future, those custom models can be upgraded to get reasoning capabilities on top of the community-specific training.

## Key Technical Concepts

**Structured Outputs**
A feature (not a separate product) that guarantees model responses match a predefined JSON schema. This means the AI's response always has the exact fields and format you specify. In your proposal, this ensures every summary, health insight, and Q&A answer comes back in a consistent, predictable format that Discord's UI can render reliably. Available on GPT-5, GPT-5 mini, GPT-5.4, GPT-4.1, and more. 100% schema compliance.

**Agents SDK**
A newer OpenAI framework for building AI agents that chain multiple tools together in orchestrated workflows. Relevant to the Discord proposal because community management agents could combine Moderation, Embeddings, and GPT-5 mini into automated pipelines (e.g., an agent that monitors a channel, checks content safety, finds related past conversations, and generates a Q&A response in one flow). The SDK handles the agent loop, tool routing, and error recovery. You don't need to go deep on this in the presentation, but if asked, it shows you know OpenAI's platform beyond individual API endpoints.

**RAG (Retrieval-Augmented Generation)**
A pattern, not a product. Instead of asking the AI to answer from its general training knowledge (which can hallucinate), you first retrieve relevant documents or past conversations, then feed those to the model as context, and ask it to answer based only on that. "Retrieval" = find relevant content using embeddings. "Augmented" = feed it to the model. "Generation" = model writes the answer. This is how Smart Q&A works in your proposal.

**Vector Database / Vector Store**
A database optimized for storing and searching embeddings. When you embed a million past Discord messages, you store those vectors here. When someone asks a question, you search this database by meaning, not keywords. Common options include Pinecone, Weaviate, or pgvector (Postgres extension). You don't need to name one in the interview, just know the concept.

**Tokens**
The unit OpenAI charges by. Roughly 750 English words = 1,000 tokens. Both input (what you send) and output (what the model generates) count. GPT-5 mini costs about 5x less per token than GPT-5 ($0.25 vs. $1.25 per million input tokens), which is why model tiering matters at scale. At Discord's volume, routing routine classification through GPT-5 mini instead of GPT-5 saves hundreds of thousands of dollars annually.

**The GPT Model Family (quick reference)**
- GPT-5.4: $2.50/$15 per MTok. Latest flagship. 1M context. Best reasoning. Released March 5, 2026.
- GPT-5: $1.25/$10 per MTok. Reasoning model. 400K context. Released August 2025.
- GPT-5 mini: $0.25/$2 per MTok. Cost-efficient. 400K context. Released August 2025.
- GPT-5 nano: $0.05/MTok input. Fastest, cheapest. For very simple tasks.
- GPT-4.1: $2/$8 per MTok. Non-reasoning model. 1M context. Supports fine-tuning.
- GPT-4.1 mini: Smaller, cheaper version of 4.1. Also supports fine-tuning.

---
---

# INTERVIEW PREP

Things you should know cold in case they go deeper in a follow-up conversation. All answers below are written as speakable sentences so you can rehearse them out loud.

## "Why Discord and not Shopify, Stripe, Roblox, or another digital-native company?"

"I chose Discord for three reasons. First, I know them. I led their platform partnership at Meta, so I have real context on how their ecosystem works and where the gaps are. Second, the use case maps to OpenAI's full product portfolio. Most companies would use one or two products. Discord can use seven across text, voice, search, and safety: GPT-5, GPT-5 mini, Whisper, the Realtime API, Embeddings, Moderation, and Fine-tuning. That makes it a larger, stickier deal with multiple expansion paths. Third, voice. Discord is the only major platform where voice is a core feature, and Whisper plus the Realtime API give OpenAI a unique advantage there that doesn't apply to Shopify or Stripe. No other company in the digital-native enterprise space gives you this kind of multi-product, consumption-based opportunity."

## "How would you actually approach this account in your first 90 days?"

"Week one, I'd map the org chart: who owns developer platform, who owns AI/ML, who owns trust and safety, who owns enterprise sales. Discord's CTO is likely the executive sponsor, but the deal will need buy-in from product, engineering, and the business side. Weeks two through four, I'd set up discovery calls with each stakeholder to understand their current AI roadmap, what they've already tried (they deprecated Clyde, their AI chatbot, in early 2024, and have since invested in AutoMod AI and server-level AI experiments), and what internal resistance looks like. I'd also identify their current AI vendors, if any, and understand where they're building in-house vs. buying. Weeks four through eight, I'd run a proof of concept focused on Conversation Catch-Up with a handful of high-value servers. Low risk, fast time to value. The goal is a working demo that makes the value obvious. Months two through three, I'd present ROI data from the POC, quantify the moderator time saved and engagement lift, and propose expanding to Voice Intelligence and Smart Q&A. That's the land-and-expand motion: start with one feature, prove it works, then systematically grow into the full seven-product partnership."

## "What's consumption revenue and why does it matter for this role?"

"Consumption revenue means OpenAI gets paid based on API usage, specifically tokens processed, not a flat subscription fee. The more Discord's users engage with AI features, the more API calls they make, and the more revenue flows to OpenAI. This role's quota is a consumption revenue target, meaning you're measured on growing usage within your accounts, not just closing deals. That's why the proposal emphasizes features that generate ongoing, growing API volume like summaries, transcriptions, and searches rather than one-time implementations. The way I think about it: my job isn't to close a contract and move on. My job is to make Discord so successful with OpenAI's products that their API usage keeps growing quarter over quarter. The incentives are aligned perfectly: the better the AI features work for Discord's users, the more API volume they generate, and the more revenue OpenAI earns."

## "Isn't Discord already building AI features?"

"Yes, and that's a good thing. Discord launched AutoMod AI for content moderation, and they previously had Clyde, an AI chatbot, which they deprecated in early 2024. The fact that they're experimenting with AI means there's internal appetite and executive support. But building and maintaining your own models is expensive and distracting from your core product. Look at what OpenAI offers from a single platform today: text reasoning with GPT-5, cost-efficient classification with GPT-5 mini, speech transcription with Whisper, live voice with the Realtime API, semantic search with Embeddings, content safety with omni-moderation, custom model training with Fine-tuning, and the Agents SDK for orchestrating all of it. Building all of that in-house would take Discord years and a massive ML team. The pitch is: let Discord focus on building community features, and let OpenAI handle the intelligence layer. It's the same argument that worked for cloud computing: don't build your own data centers, use AWS. Here it's: don't train your own models, use OpenAI."

## "What if they say they want to use Anthropic or Google instead?"

"Fair question. I'd approach it in two parts. First, the product breadth argument. No one else covers text reasoning, voice transcription, live audio, semantic search, content moderation, custom fine-tuning, and structured outputs from one platform. Anthropic is strong on text reasoning but has no speech-to-text product, no equivalent to Whisper, no Realtime API for live voice. Google has Gemini with speech capabilities, but their moderation tooling is fragmented compared to OpenAI's single omni-moderation endpoint, and they don't have the Realtime API's low-latency WebRTC and SIP integration for live voice. For Discord's use case, you'd need to stitch together multiple vendors to get what OpenAI provides out of the box, and that creates integration complexity, multiple billing relationships, and no single partner to hold accountable.

Second, the relationship argument. At the Account Director level, you don't just win on features. You embed into their roadmap. You run joint engineering sessions. You help them build custom fine-tuned models that create real switching costs. You make OpenAI the default platform their developers reach for. The technical advantage gets you in the door. The partnership, the trust, the embedded workflows, that's what keeps you there."

## "Walk me through the consumption math."

"Let's use conservative numbers. Discord has around 19 million active servers. Assume 5% adopt AI features. That's 950,000 servers. An average active server might generate 500 messages per day. If even 10% of those messages trigger some model call, whether that's classification, summarization, or search, that's around 47 million API calls per day.

Now let's put pricing on it. A typical message is about 200 tokens. At GPT-5 mini's rate of $0.25 per million input tokens, 47 million calls at 200 tokens each is roughly 9.4 billion input tokens per day, which works out to about $2,350 per day just on text classification. That's roughly $860,000 per year on the cheapest, simplest model call alone.

But that's just the floor. Layer on top of that: channel summaries using GPT-5 at $1.25 per million tokens for the complex multi-day analysis. Voice transcription with Whisper, which generates much higher per-call revenue than text classification. Embeddings for every message that goes into the semantic search index. Moderation checks on every message, which are free but drive platform stickiness.

Conservatively, you're looking at a multi-million dollar annual contract. And the growth lever is clear: as more servers adopt, as voice features roll out, as enterprise customers come online, the volume compounds. That's the beauty of a consumption deal. You don't renegotiate the contract for more money. The revenue grows organically as Discord's users engage more with the AI features."

## "GPT-5.4 just launched last week. How does that change the proposal?"

"Great question. GPT-5.4 launched March 5th and it's the most capable model OpenAI has ever released, with a million-token context window, native computer-use capabilities, and the highest reasoning scores to date. For Discord's use case, GPT-5.4 would be relevant for the most complex analytical tasks, like generating multi-day thread summaries across hundreds of messages or powering the Community Health Insights feature where admins ask open-ended questions about their server. That million-token context window is especially interesting because a busy Discord server can generate that much content in just a few days, meaning GPT-5.4 could analyze an entire week of server activity in a single call.

But for the high-volume work like message classification and daily digests, GPT-5 mini at $0.25 per million tokens is the right fit. You don't need frontier reasoning to decide whether a message should be classified as an announcement vs. a casual conversation. That cost discipline is what makes the deal viable at Discord's scale. The beauty of OpenAI's model family is that Discord can route different tasks to different models and upgrade specific workflows to GPT-5.4 as the value justifies the cost. It's not one model or the other. It's the right model for each job."

## "Which model would Discord fine-tune?"

"Right now, fine-tuning is available on GPT-4.1 and GPT-4.1 mini. GPT-5 models don't support fine-tuning yet. For Discord's use case, fine-tuning GPT-4.1 mini is actually a smart starting point. 4.1 mini is fast, cost-efficient, and purpose-built for tool calling and instruction following. It's exactly what you want for tasks like understanding community-specific slang, calibrating relevance signals for a particular server's norms, or tuning moderation sensitivity for different community types. A gaming server and an enterprise developer community have very different standards for what's appropriate, and fine-tuning lets you adapt to each.

The roadmap story is strong too. As OpenAI expands fine-tuning support to GPT-5 models, Discord could upgrade those custom models to get reasoning capabilities on top of the community-specific training they've already built. That's a natural expansion path within the account: start with fine-tuned 4.1 mini for routine tasks, then migrate to fine-tuned GPT-5 for more complex understanding. Each step generates more API consumption and deepens the integration."

## "What about the Agents SDK? Should Discord use it?"

"The Agents SDK is newer and very relevant here. Think of it this way: the seven products in the proposal are the individual building blocks. The Agents SDK is how you wire them together into automated workflows.

For example, Discord could build a community management agent that monitors a channel, calls the Moderation API to check incoming content for policy violations, uses the Embeddings API to find related past conversations, and then generates a Q&A response or a summary using GPT-5 mini, all in a single orchestrated flow. The SDK handles the agent loop, decides which tools to call and in what order, and manages error recovery if something fails.

For the proposal, I focused on the individual API products because that's where the consumption revenue lives and it's easier to reason about. But the Agents SDK is how Discord would actually build this in production. And it makes the integration stickier because they're not just calling individual endpoints; they're building agent workflows on top of OpenAI's infrastructure. Moving off that platform means re-architecting their entire agent orchestration layer, not just swapping out a model."

## "How do you handle a champion who leaves the account?"

"This is why you never build a deal around a single person. From the start, I'd make sure we have relationships with at least three stakeholders: the technical champion, the business sponsor, and the end-user advocate, usually a community lead or product manager who sees the daily impact. I'd also make sure the POC results and ROI data are documented and shared broadly, not just in someone's inbox. If a champion leaves, the data speaks for itself. And the fine-tuned models, the embedded integrations, the agent workflows, those don't leave with the person. The switching costs are built into the infrastructure, not the relationship."

## Discord Quick Facts

- Founded: 2015
- Monthly active users: 200M+
- Annual revenue: ~$600M+ (primarily Nitro subscriptions)
- CEO: Jason Citron
- Headquarters: San Francisco
- Key competitors for community: Slack (Salesforce), Teams (Microsoft), Guilded (Roblox)
- Their AI history: Launched Clyde (ChatGPT-powered bot) in March 2023, deprecated it in early 2024. Launched AI-powered AutoMod. Has since continued investing in server-level AI experiments, signaling continued executive appetite for AI features.
- Enterprise push: Increasingly used by developer relations teams, open-source projects, crypto/web3 communities, education institutions, and brands for community management.
- Key engineering fact: Discord runs on Elixir/Erlang for real-time messaging and Rust for performance-critical services. Their engineering blog is excellent and shows a team that cares about scale.

## Things NOT to Say

- Don't say "I'm not technical" without immediately following up with a technical point. Say "I'm not an engineer, but..." and then demonstrate reasoning. The script does this.
- Don't oversell. Don't say "this will definitely work." Say "based on comparable deployments" or "the architecture is designed to mitigate this."
- Don't badmouth competitors. Say "OpenAI has a unique advantage here" rather than "Anthropic can't do this."
- Don't quote specific dollar amounts for the deal size. Say "multi-million dollar annual contract" and let them size it.
- Don't claim you'll close Discord in Q1. This is a thought exercise about how you think, not a sales commitment.
- Don't say "GPT-4o" or "GPT-4" in conversation. Those are previous generation. If you accidentally say it, correct yourself: "sorry, GPT-5 mini."
- Don't claim fine-tuning works on GPT-5 models. It doesn't yet. Say "GPT-4.1" or "GPT-4.1 mini" when talking about fine-tuning.
- Say "GPT five-four" not "GPT five point four" (that's how OpenAI people say it).
- Don't confuse the Realtime API with Whisper. Whisper processes recorded audio after the fact. The Realtime API handles live, streaming audio. They're complementary products, not the same thing.
