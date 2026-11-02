import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { shouldUseSecureAuthCookie } from "../auth-cookie";
import { isAllowedAuthOrigin } from "../auth-origin";

export async function POST(request: NextRequest) {
  if (!isAllowedAuthOrigin(request)) {
    return NextResponse.json({ success: false, error: "Origin không hợp lệ." }, { status: 403 });
  }
  const response = NextResponse.json({ success: true });
  response.cookies.set("baha_auth_token", "", {
    path: "/",
    maxAge: 0,
    sameSite: "lax",
    httpOnly: true,
    secure: shouldUseSecureAuthCookie(),
  });
  return response;
}
