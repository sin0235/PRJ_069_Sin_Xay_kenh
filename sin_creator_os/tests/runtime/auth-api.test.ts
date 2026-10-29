import { AuthApi } from "../../src/lib/api/auth-api.ts";
import assert from "node:assert/strict";
import { test } from "node:test";

function installBrowserStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    },
  });
  return {
    values,
    restore() {
      if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
      else delete (globalThis as typeof globalThis & { window?: unknown }).window;
    },
  };
}

test("refreshSession validates the cookie and hydrates a tab without local storage", async () => {
  const browser = installBrowserStorage();
  const originalFetch = globalThis.fetch;
  const session = {
    user: { id: "user-1", email: "owner@example.test", full_name: "Owner", role: "WORKSPACE_OWNER" },
    workspace: { id: "workspace-1", name: "Studio" },
    workspace_id: "workspace-1",
  };
  assert.equal(AuthApi.isAuthenticated(), false);
  assert.equal(AuthApi.getAuthToken(), "");
  globalThis.fetch = (async (input, init) => {
    assert.equal(String(input), "/v1/auth/me");
    assert.equal(init?.method, "GET");
    assert.equal(init?.credentials, "same-origin");
    assert.equal(init?.cache, "no-store");
    const requestHeaders = new Headers(init?.headers);
    assert.equal(requestHeaders.get("X-Workspace-Id"), null);
    assert.equal(requestHeaders.get("Authorization"), null);
    return new Response(JSON.stringify(session), { status: 200 });
  }) as typeof fetch;

  try {
    const result = await AuthApi.refreshSession();

    assert.deepEqual(result, { user: session.user, workspace: session.workspace });
    assert.equal(browser.values.get("baha_workspace_id"), "workspace-1");
    assert.deepEqual(JSON.parse(browser.values.get("baha_user_profile") || "null"), session.user);
    assert.equal(AuthApi.getCurrentUser().role, "WORKSPACE_OWNER");
    assert.equal(AuthApi.isAuthenticated(), true);
  } finally {
    globalThis.fetch = originalFetch;
    browser.restore();
  }
});

test("refreshSession clears stale display data when the cookie is rejected", async () => {
  const browser = installBrowserStorage({
    baha_workspace_id: "stale-workspace",
    baha_user_profile: JSON.stringify({ id: "stale-user", role: "WORKSPACE_OWNER" }),
  });
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () => new Response("{}", { status: 401 })) as typeof fetch;

  try {
    assert.equal(await AuthApi.refreshSession(), null);
    assert.equal(browser.values.has("baha_workspace_id"), false);
    assert.equal(browser.values.has("baha_user_profile"), false);
  } finally {
    globalThis.fetch = originalFetch;
    browser.restore();
  }
});

test("refreshSession can hydrate a valid cookie when browser storage is unavailable", async () => {
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const originalFetch = globalThis.fetch;
  Object.defineProperty(globalThis, "window", { configurable: true, value: {} });
  let requested = false;
  globalThis.fetch = (async () => {
    requested = true;
    return new Response(
      JSON.stringify({
        user: { id: "user-no-storage", email: "owner@example.test", full_name: "Owner", role: "WORKSPACE_OWNER" },
        workspace: { id: "workspace-no-storage", name: "Studio" },
      }),
      { status: 200 },
    );
  }) as typeof fetch;

  try {
    const result = await AuthApi.refreshSession();

    assert.equal(requested, true);
    assert.equal(result?.user.id, "user-no-storage");
    assert.equal(AuthApi.getCurrentUser().role, "WORKSPACE_OWNER");
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else delete (globalThis as typeof globalThis & { window?: unknown }).window;
  }
});
