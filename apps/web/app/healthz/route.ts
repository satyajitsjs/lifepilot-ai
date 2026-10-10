import { forwardToApi } from "@/lib/server-api-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  return forwardToApi(request, "healthz");
}
