import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json(
    { success: false, error: "Đăng nhập được xử lý bởi Cloudflare Access bằng mã OTP." },
    { status: 410 },
  );
}
