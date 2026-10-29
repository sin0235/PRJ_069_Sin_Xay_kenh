import assert from "node:assert/strict";
import { test } from "node:test";
import { getApiBaseUrl } from "../../src/lib/api/base-url.ts";

test("browser API calls stay on the page origin", () => {
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const originalApiUrl = process.env.API_INTERNAL_URL;
  process.env.API_INTERNAL_URL = "http://api:8000";
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location: { origin: "https://studio.example" } },
  });

  try {
    assert.equal(getApiBaseUrl(), "https://studio.example");
  } finally {
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else delete (globalThis as typeof globalThis & { window?: unknown }).window;
    if (originalApiUrl === undefined) delete process.env.API_INTERNAL_URL;
    else process.env.API_INTERNAL_URL = originalApiUrl;
  }
});

test("server API calls use and normalize the internal service URL", () => {
  const originalApiUrl = process.env.API_INTERNAL_URL;
  process.env.API_INTERNAL_URL = "http://api:8000///";

  try {
    assert.equal(getApiBaseUrl(), "http://api:8000");
  } finally {
    if (originalApiUrl === undefined) delete process.env.API_INTERNAL_URL;
    else process.env.API_INTERNAL_URL = originalApiUrl;
  }
});
