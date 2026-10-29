import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { shouldUseSecureAuthCookie } from "../auth-cookie";
import { isAllowedAuthOrigin } from "../auth-origin";

export async function POST(request: NextRequest) {
  if (!isAllowedAuthOrigin(request)) {
    return NextResponse.json({ success: false, error: "Origin không hợp lệ." }, { status: 403 });
  }

  const apiInternalUrl = process.env.API_INTERNAL_URL;
  if (!apiInternalUrl) {
    return NextResponse.json({ success: false, error: "Máy chủ xác thực chưa được cấu hình." }, { status: 503 });
  }

  try {
    const apiBase = new URL(apiInternalUrl);
    if (
      !new Set(["http:", "https:"]).has(apiBase.protocol) ||
      apiBase.username ||
      apiBase.password ||
      apiBase.search ||
      apiBase.hash ||
      apiBase.pathname !== "/"
    ) {
      return NextResponse.json({ success: false, error: "Máy chủ xác thực chưa được cấu hình." }, { status: 503 });
    }

    const body = await request.json();
    const response = await fetch(new URL("/auth/login", apiBase), {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Origin: request.headers.get("origin") || "",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(
        { success: false, error: data.detail?.message_safe || data.detail || "Email hoặc mật khẩu không chính xác." },
        { status: response.status },
      );
    }
    if (!data.access_token || !data.user?.id || !data.workspace?.id) {
      return NextResponse.json(
        { success: false, error: "Máy chủ xác thực trả về hồ sơ không hợp lệ." },
        { status: 502 },
      );
    }

    const result = NextResponse.json({ success: true, user: data.user, workspace: data.workspace });
    result.cookies.set("baha_auth_token", data.access_token, {
      path: "/",
      maxAge: 60 * 60 * 8,
      sameSite: "lax",
      httpOnly: true,
      secure: shouldUseSecureAuthCookie(),
    });
    return result;
  } catch {
    return NextResponse.json({ success: false, error: "Không thể kết nối đến máy chủ xác thực." }, { status: 503 });
  }
}
