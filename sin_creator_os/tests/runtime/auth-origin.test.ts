import { isAllowedAuthOrigin } from "../../src/app/api/auth/auth-origin.ts";
import assert from "node:assert/strict";
import test from "node:test";

function authRequest(origin: string) {
  return {
    headers: new Headers({ origin }),
    nextUrl: new URL("https://studio.example.test/dashboard"),
  } as unknown as Parameters<typeof isAllowedAuthOrigin>[0];
}

test("configured auth origins reject path slashes", () => {
  const previous = process.env.AUTH_ALLOWED_ORIGINS;
  process.env.AUTH_ALLOWED_ORIGINS = "https://studio.example.test/";
  try {
    assert.equal(isAllowedAuthOrigin(authRequest("https://studio.example.test")), false);
  } finally {
    if (previous === undefined) delete process.env.AUTH_ALLOWED_ORIGINS;
    else process.env.AUTH_ALLOWED_ORIGINS = previous;
  }
});

test("request Origin must be a serialized origin without a path slash", () => {
  const previous = process.env.AUTH_ALLOWED_ORIGINS;
  process.env.AUTH_ALLOWED_ORIGINS = "https://studio.example.test";
  try {
    assert.equal(isAllowedAuthOrigin(authRequest("https://studio.example.test/")), false);
  } finally {
    if (previous === undefined) delete process.env.AUTH_ALLOWED_ORIGINS;
    else process.env.AUTH_ALLOWED_ORIGINS = previous;
  }
});
