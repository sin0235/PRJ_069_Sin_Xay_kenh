import type { NextRequest } from "next/server";

export function isAllowedAuthOrigin(request: NextRequest): boolean {
  const rawOrigin = request.headers.get("origin");
  if (!rawOrigin) return false;

  let origin: URL;
  try {
    origin = new URL(rawOrigin);
  } catch {
    return false;
  }
  if (
    rawOrigin !== origin.origin ||
    origin.pathname !== "/" ||
    origin.search ||
    origin.hash ||
    origin.username ||
    origin.password
  ) {
    return false;
  }

  const configured = (process.env.AUTH_ALLOWED_ORIGINS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (configured.length) {
    const allowed = new Set<string>();
    for (const value of configured) {
      try {
        const url = new URL(value);
        if (
          !new Set(["http:", "https:"]).has(url.protocol) ||
          url.pathname !== "/" ||
          value.endsWith("/") ||
          url.search ||
          url.hash ||
          url.username ||
          url.password
        ) {
          return false;
        }
        allowed.add(url.origin);
      } catch {
        return false;
      }
    }
    return allowed.has(origin.origin);
  }

  return process.env.NODE_ENV !== "production" && origin.origin === request.nextUrl.origin;
}
