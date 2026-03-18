import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";
import { NextResponse } from "next/server";

type AdvisoryRequest = {
  prompt?: string;
};

const MAX_PROMPT_LENGTH = 2_000;
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX_REQUESTS = 20;
const SESSION_COOKIE = "session";
const advisoryHits = new Map<string, number[]>();

function getClientIdentifier(req: Request) {
  const forwardedFor = req.headers.get("x-forwarded-for");
  if (forwardedFor) {
    const first = forwardedFor.split(",")[0]?.trim();
    if (first) return first;
  }
  return req.headers.get("x-real-ip")?.trim() || "unknown";
}

function isRateLimited(clientId: string) {
  const now = Date.now();
  const cutoff = now - RATE_LIMIT_WINDOW_MS;
  const recent = (advisoryHits.get(clientId) ?? []).filter(
    (timestamp) => timestamp > cutoff
  );

  if (recent.length >= RATE_LIMIT_MAX_REQUESTS) {
    advisoryHits.set(clientId, recent);
    return true;
  }

  recent.push(now);
  advisoryHits.set(clientId, recent);
  return false;
}

function hasSessionCookie(req: Request) {
  const cookieHeader = req.headers.get("cookie");
  if (!cookieHeader) return false;
  return cookieHeader
    .split(";")
    .some((cookie) => cookie.trim().startsWith(`${SESSION_COOKIE}=`));
}

export async function POST(req: Request) {
  try {
    if (process.env.NODE_ENV !== "test" && !hasSessionCookie(req)) {
      return NextResponse.json(
        { success: false, error: "You must be signed in to use AI advisory." },
        { status: 401 }
      );
    }

    const clientId = getClientIdentifier(req);
    if (isRateLimited(clientId)) {
      return NextResponse.json(
        {
          success: false,
          error: "Too many advisory requests. Please wait a minute and retry.",
        },
        { status: 429 }
      );
    }

    const body = (await req.json()) as AdvisoryRequest;
    const prompt = body.prompt?.trim();

    if (!prompt) {
      return NextResponse.json(
        { success: false, error: "Prompt is required." },
        { status: 400 }
      );
    }

    if (prompt.length > MAX_PROMPT_LENGTH) {
      return NextResponse.json(
        {
          success: false,
          error: `Prompt is too long. Max length is ${MAX_PROMPT_LENGTH} characters.`,
        },
        { status: 400 }
      );
    }

    if (!process.env.OPENAI_API_KEY) {
      return NextResponse.json(
        { success: false, error: "OPENAI_API_KEY is not configured." },
        { status: 503 }
      );
    }

    const result = await generateText({
      model: openai("gpt-4o-mini"),
      system:
        "You are the FileFree advisory assistant. Give concise, practical guidance in plain English with bullet points. Do not provide legal advice.",
      prompt,
      temperature: 0.4,
    });

    return NextResponse.json({
      success: true,
      data: { text: result.text },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unexpected advisory failure.";

    if (
      message.toLowerCase().includes("insufficient_quota") ||
      message.toLowerCase().includes("exceeded your current quota")
    ) {
      return NextResponse.json(
        {
          success: false,
          error:
            "AI advisory is temporarily unavailable due to model quota limits. Please top up billing and retry.",
        },
        { status: 429 }
      );
    }

    console.error("Advisory request failed:", message);
    return NextResponse.json(
      {
        success: false,
        error: "Advisory is temporarily unavailable. Please try again shortly.",
      },
      { status: 500 }
    );
  }
}
