import { forwardToApi } from "@/lib/server-api-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, { params }: Context): Promise<Response> {
  const { path } = await params;
  // Prevent URL normalization from reaching private /internal/ routes.
  if (!path.length || path.some(segment =>
    segment === "." || segment === ".." ||
    segment.includes("/") || segment.includes("\\") || segment.includes("%")
  )) {
    return Response.json({ detail: "Invalid API path" }, { status: 400 });
  }
  return forwardToApi(request, `api/${path.map(encodeURIComponent).join("/")}`);
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE, proxy as OPTIONS, proxy as HEAD };
