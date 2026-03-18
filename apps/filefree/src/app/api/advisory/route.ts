import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";
import { NextResponse } from "next/server";

type AdvisoryRequest = {
  prompt?: string;
};

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as AdvisoryRequest;
    const prompt = body.prompt?.trim();

    if (!prompt) {
      return NextResponse.json(
        { success: false, error: "Prompt is required." },
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

    return NextResponse.json(
      { success: false, error: `Advisory request failed: ${message}` },
      { status: 500 }
    );
  }
}
