import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type AskBody = {
  node_id: string;
  label: string;
  module_path: string;
  description?: string;
};

export async function POST(request: Request) {
  const brainUrl = process.env.BRAIN_API_URL?.trim();
  const brainSecret = process.env.BRAIN_API_SECRET?.trim();

  if (!brainUrl || !brainSecret) {
    return NextResponse.json(
      { error: "Brain is not wired — set BRAIN_API_URL and BRAIN_API_SECRET." },
      { status: 503 },
    );
  }

  let body: AskBody;
  try {
    body = (await request.json()) as AskBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const message = [
    `I'm standing in the Studio command center DAG looking at "${body.label}" (id: ${body.node_id}, path: ${body.module_path}).`,
    body.description ? `Short description: ${body.description}` : null,
    "Explain in 5-8 lines:",
    "1) What this service does in plain language.",
    "2) What depends on it and what it depends on.",
    "3) Any recent activity, deploys, or incidents you can find in memory.",
    "4) The single most important thing I should know before touching it.",
  ]
    .filter(Boolean)
    .join("\n");

  try {
    const res = await fetch(`${brainUrl.replace(/\/$/, "")}/api/v1/brain/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Brain-Secret": brainSecret,
      },
      body: JSON.stringify({
        organization_id: "paperwork",
        channel: "studio",
        message,
      }),
      signal: AbortSignal.timeout(30_000),
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return NextResponse.json(
        {
          error: `Brain returned HTTP ${res.status}`,
          detail: detail.slice(0, 500),
        },
        { status: 502 },
      );
    }

    const json = (await res.json()) as {
      data?: { response?: string; persona?: string; model?: string };
      response?: string;
    };

    const responseText =
      json.data?.response ?? json.response ?? "Brain returned no content.";
    const persona = json.data?.persona;
    const model = json.data?.model;
    const footer =
      persona || model
        ? `\n\n— via Brain · ${[persona, model].filter(Boolean).join(" · ")}`
        : "";

    return NextResponse.json({
      response: responseText + footer,
    });
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? `Brain request failed: ${err.message}`
            : "Brain request failed",
      },
      { status: 502 },
    );
  }
}
