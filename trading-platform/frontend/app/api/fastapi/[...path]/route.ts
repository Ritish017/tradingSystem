import { NextRequest, NextResponse } from "next/server";

const backendBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://backend:8000";

async function proxy(request: NextRequest, params: { path: string[] }) {
  const targetPath = params.path.join("/");
  const search = request.nextUrl.search;
  const target = `${backendBase}/${targetPath}${search}`;

  const upstream = await fetch(target, {
    method: request.method,
    headers: request.headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text()
  });

  const body = await upstream.text();
  return new NextResponse(body, { status: upstream.status });
}

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxy(request, params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxy(request, params);
}

