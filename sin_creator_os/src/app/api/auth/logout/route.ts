import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ success: true });
  response.cookies.set("baha_auth_token", "", {
    path: "/",
    maxAge: 0,
    sameSite: "lax",
  });
  return response;
}
