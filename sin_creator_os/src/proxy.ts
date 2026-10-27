import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const forwardedHeaders = new Headers(request.headers);
  forwardedHeaders.delete("x-sin-dev-auth-bypass");
  const appEnv = process.env.APP_ENV?.toLowerCase();
  const host = request.nextUrl.hostname.toLowerCase();
  const isLoopback = host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host === "::1";
  const devAuthBypass = process.env.DEV_AUTH_BYPASS === "1"
    && ["offline", "development", "dev", "local", "test"].includes(appEnv || "")
    && isLoopback;
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
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
