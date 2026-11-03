import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const forwardedHeaders = new Headers(request.headers);
  forwardedHeaders.delete("x-sin-dev-auth-bypass");

  if (pathname === "/v1" || pathname.startsWith("/v1/")) {
    const apiInternalUrl = process.env.API_INTERNAL_URL;
    if (apiInternalUrl) {
      try {
        const target = new URL(apiInternalUrl);
        if (
          !new Set(["http:", "https:"]).has(target.protocol) ||
          target.username ||
          target.password ||
          target.pathname !== "/" ||
          target.search ||
          target.hash
        ) {
          return NextResponse.json({ detail: "API nội bộ chưa được cấu hình hợp lệ." }, { status: 503 });
        }
        target.pathname = pathname;
        target.search = request.nextUrl.search;
        return NextResponse.rewrite(target, { request: { headers: forwardedHeaders } });
      } catch {
        return NextResponse.json({ detail: "API nội bộ chưa được cấu hình hợp lệ." }, { status: 503 });
      }
    }
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json({ detail: "API nội bộ chưa được cấu hình." }, { status: 503 });
    }
  }

  const appEnv = process.env.APP_ENV?.toLowerCase();
  const host = request.nextUrl.hostname.toLowerCase();
  const isLoopback = host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host === "::1";
  const devAuthBypass =
    process.env.DEV_AUTH_BYPASS === "1" &&
    ["offline", "development", "dev", "local", "test"].includes(appEnv || "") &&
    isLoopback;
  if (devAuthBypass) forwardedHeaders.set("x-sin-dev-auth-bypass", "1");

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/opengraph") ||
    pathname.startsWith("/twitter") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  if (devAuthBypass && pathname.startsWith("/auth/")) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  const token = request.cookies.get("baha_auth_token")?.value;
  if (token && pathname === "/") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next({ request: { headers: forwardedHeaders } });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
