import { forwardToApi } from "@/lib/server-api-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, { params }: Context): Promise<Response> {
  const { path } = await params;
  return forwardToApi(request, `api/${path.map(encodeURIComponent).join("/")}`);
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE, proxy as OPTIONS, proxy as HEAD };
