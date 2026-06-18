import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

async function handler(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000";
  const search = new URL(req.url).search;
  const target = `${base}/${path.join("/")}${search}`;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = process.env.API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const upstream = await fetch(target, init);
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

export { handler as GET, handler as POST };
