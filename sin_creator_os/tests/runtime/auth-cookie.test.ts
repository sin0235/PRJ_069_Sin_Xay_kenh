import { shouldUseSecureAuthCookie } from "../../src/app/api/auth/auth-cookie.ts";
import assert from "node:assert/strict";
import test from "node:test";

test("production auth cookies are Secure by default", () => {
  assert.equal(shouldUseSecureAuthCookie({ NODE_ENV: "production" }), true);
});

test("explicit insecure cookies are permitted for local HTTP production origins", () => {
  assert.equal(shouldUseSecureAuthCookie({ NODE_ENV: "production", AUTH_COOKIE_SECURE: "false" }), false);
});

test("development cookies default to non-Secure unless explicitly enabled", () => {
  assert.equal(shouldUseSecureAuthCookie({ NODE_ENV: "development" }), false);
  assert.equal(shouldUseSecureAuthCookie({ NODE_ENV: "development", AUTH_COOKIE_SECURE: "true" }), true);
});
