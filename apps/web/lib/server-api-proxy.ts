/** Server-only gateway to the FastAPI Vercel service binding. */
import "server-only";

const requestHeaders = ["authorization", "accept", "content-type"];
const responseHeaders = ["content-type", "content-disposition", "cache-control"];

export async function forwardToApi(request: Request, path: string): Promise<Response> {
  // Vercel injects API_SERVICE_URL at runtime. API_BACKEND_URL is for Docker.
  const base = process.env.API_SERVICE_URL || process.env.API_BACKEND_URL ||
    (process.env.VERCEL ? undefined : "http://127.0.0.1:8000");
  if (!base) {
    return Response.json({ detail: "API service binding is not configured" }, { status: 503 });
  }
  let url: URL;
  try {
    url = new URL(path.replace(/^\/+/, ""), base.replace(/\/+$/, "") + "/");
    url.search = new URL(request.url).search;
  } catch {
    return Response.json({ detail: "Invalid API service configuration" }, { status: 503 });
  }
  const headers = new Headers();
  for (const name of requestHeaders) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });
    const outbound = new Headers();
    for (const name of responseHeaders) {
      const value = upstream.headers.get(name);
      if (value !== null) outbound.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: outbound });
  } catch {
    return Response.json({ detail: "API service is unavailable" }, { status: 502 });
  }
}
