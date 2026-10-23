import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const res = await fetch("http://127.0.0.1:8000/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        { success: false, error: data.detail || "Email hoặc mật khẩu không chính xác." },
        { status: res.status }
      );
    }

    const response = NextResponse.json({
      success: true,
      token: data.access_token,
      user: data.user,
      workspace: data.workspace,
    });

    // Thiết lập cookie HTTP để Middleware và Server nhận diện ngay lập tức
    response.cookies.set("baha_auth_token", data.access_token, {
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 ngày
      sameSite: "lax",
      httpOnly: false,
    });

    return response;
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: "Không thể kết nối đến máy chủ xác thực Backend (127.0.0.1:8000)." },
      { status: 500 }
    );
  }
}
