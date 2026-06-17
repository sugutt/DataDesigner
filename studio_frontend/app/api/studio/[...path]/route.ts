import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.STUDIO_API_BASE ?? "http://localhost:8000";
const ADMIN_TOKEN = process.env.STUDIO_ADMIN_TOKEN ?? "dev-token";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

async function proxy(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  const upstream = new URL(`/api/${params.path.join("/")}${request.nextUrl.search}`, API_BASE);
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const response = await fetch(upstream, {
    method: request.method,
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": request.headers.get("content-type") ?? "application/json",
    },
    body,
  });
  const headers = new Headers(response.headers);
  headers.delete("content-encoding");
  return new NextResponse(response.body, {
    status: response.status,
    headers,
  });
}
