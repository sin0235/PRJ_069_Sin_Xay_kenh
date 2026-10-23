import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const DEFAULT_DEV_TOKEN =
  "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidXNyX3Npbl9vd25lciIsICJpc3MiOiAiYmFoYS1hdXRoLWlzc3VlciIsICJhdWQiOiAic2luLWNvbnRlbnQtdGVzdCIsICJleHAiOiAxNzk1MjQwNDk1LCAid29ya3NwYWNlX2lkIjogImRlZmF1bHRfd3MiLCAiZW1haWwiOiAic2luQHRlc3QuY29tIiwgIm5hbWUiOiAiU2luIEFkbWluIChIaWdoZXN0IFByaXZpbGVnZSkiLCAicm9sZSI6ICJXT1JLU1BBQ0VfT1dORVIifQ.GkPn-kYGz_8YBUMxVT9cY1P8L38pshYpiqP6VR7YyFA";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Cho phép tài nguyên tĩnh, build chunk và public assets
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

  // 2. Lấy token xác thực từ Cookie
  let token = request.cookies.get("baha_auth_token")?.value;

  // 3. Nếu chưa có cookie xác thực: tự động gắn token Quản trị tối cao (sin@test.com)
  if (!token && !pathname.startsWith("/auth/")) {
    const response = NextResponse.next();
    response.cookies.set("baha_auth_token", DEFAULT_DEV_TOKEN, {
      path: "/",
      maxAge: 2592000,
      sameSite: "lax",
    });
    return response;
  }

  // 4. Nếu đã có token và truy cập trang chủ -> chuyển vào Dashboard
  if (token && pathname === "/") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
