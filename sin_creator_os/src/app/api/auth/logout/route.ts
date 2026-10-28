import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function POST(request: NextRequest) {
  return NextResponse.redirect(new URL("/cdn-cgi/access/logout", request.url), 303);
}
