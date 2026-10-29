import ts from "typescript";

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("../../src/lib/api/media-studio-api.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;

function loadApi(fetchRequest: typeof fetch, open: (...args: unknown[]) => void = () => {}) {
  const exports: Record<string, unknown> = {};
  runInNewContext(compiled, {
    exports,
    require(id: string) {
      if (id === "@/lib/api/auth-api") return {
        AuthApi: {
          getWorkspaceId: () => "workspace-media",
          getAuthHeaders: () => ({ "Content-Type": "application/json", Authorization: "Bearer " }),
        },
      };
      if (id === "@/lib/api/base-url") return { getApiBaseUrl: () => "https://studio.test" };
      throw new Error(`Unexpected module: ${id}`);
    },
    fetch: fetchRequest,
    FormData,
    crypto: globalThis.crypto,
    window: { open },
    setTimeout: (callback: () => void) => callback(),
  });
  return exports.mediaStudioApi as typeof import("../../src/lib/api/media-studio-api").mediaStudioApi;
}

type MediaJobFailure = Error & {
  jobId?: string;
  errorCode?: string;
  canResume?: boolean;
  resumeUrl?: string;
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

test("video enqueue polls the job and output asset using cookies without an empty Bearer", async () => {
  const urls: string[] = [];
  const replies = [
    json({ job_id: "job-video", state: "QUEUED" }, 202),
    json({ state: "SUCCEEDED", output_asset_ids: ["asset-video"] }),
    json({ id: "asset-video", url: "/v1/media/assets/asset-video/download" }),
  ];
  const api = loadApi((async (input, init) => {
    urls.push(String(input));
    assert.equal(init?.credentials, "include");
    const headers = new Headers(init?.headers);
    assert.equal(headers.get("Authorization"), null);
    assert.equal(headers.get("X-Workspace-Id"), "workspace-media");
    assert.equal(headers.get("Content-Type"), null);
    return replies.shift()!;
  }) as typeof fetch);

  const asset = await api.generateVideo({ prompt: "A landscape", idempotency_key: "video-request" });

  assert.equal(asset.id, "asset-video");
  assert.equal(asset.url, "https://studio.test/v1/media/assets/asset-video/download");
  assert.deepEqual(urls, [
    "https://studio.test/v1/media/video/generate",
    "https://studio.test/v1/ai-jobs/job-video",
    "https://studio.test/v1/media/assets/asset-video",
  ]);
});

for (const [state, errorCode, canResume] of [
  ["BLOCKED_FLOW_LOGIN", "FLOW_LOGIN_REQUIRED", true],
  ["BLOCKED_FLOW_QUOTA", "FLOW_QUOTA_LIMITED", true],
  ["NEEDS_RECONCILIATION", "FLOW_QUOTA_LIMITED", false],
] as const) {
  test(`${state} preserves the job and exposes whether it can safely resume`, async () => {
    const replies = [
      json({ job_id: "job-blocked", state: "QUEUED" }, 202),
      json({ state, error_code: errorCode, error_message: "Provider needs attention" }),
    ];
    const api = loadApi((async () => replies.shift()!) as typeof fetch);

    await assert.rejects(
      api.generateMusic({ prompt: "A piano loop", idempotency_key: "music-request" }),
      (error: unknown) => {
        const failure = error as MediaJobFailure;
        assert.equal(failure.jobId, "job-blocked");
        assert.equal(failure.errorCode, errorCode);
        assert.equal(failure.canResume, canResume);
        assert.equal(failure.resumeUrl, canResume ? "/flow-sessions" : undefined);
        return true;
      },
    );
  });
}

test("resume uses the same job ID with a selected profile and polls its output", async () => {
  const requests: Array<[string, string | undefined]> = [];
  const replies = [
    json({ job_id: "job-same", state: "QUEUED" }, 202),
    json({ state: "SUCCEEDED", asset: { id: "asset-resumed" } }),
  ];
  const api = loadApi((async (input, init) => {
    requests.push([String(input), init?.method]);
    assert.equal(init?.credentials, "include");
    return replies.shift()!;
  }) as typeof fetch);

  assert.equal((await api.resumeAiJob("job-same", { profile_id: "profile-new" })).id, "asset-resumed");
  assert.deepEqual(requests, [
    ["https://studio.test/v1/ai-jobs/job-same/resume?profile_id=profile-new", "POST"],
    ["https://studio.test/v1/ai-jobs/job-same", undefined],
  ]);
});

test("legacy music recovery exposes the blocked job immediately for manual resume", async () => {
  let calls = 0;
  const controller = new AbortController();
  const api = loadApi((async () => {
    calls += 1;
    if (calls > 1) {
      controller.abort();
      throw new Error("Blocked jobs must stop polling");
    }
    return json({ job_id: "job-recovered", state: "BLOCKED_FLOW_QUOTA", error_code: "FLOW_QUOTA_LIMITED" });
  }) as typeof fetch);

  await assert.rejects(api.waitForMusicResult("original-request", controller.signal), (error: unknown) => {
    const failure = error as MediaJobFailure;
    assert.equal(failure.jobId, "job-recovered");
    assert.equal(failure.canResume, true);
    return true;
  });
  assert.equal(calls, 1);
});

test("Flow login opens the web profile manager during the click without calling the API", async () => {
  const opened: unknown[][] = [];
  const api = loadApi((async () => { throw new Error("Login navigation must not start a server process"); }) as typeof fetch,
    (...args) => opened.push(args));

  const pending = api.openGoogleFlowLogin();

  assert.deepEqual(opened, [["/flow-sessions", "_blank", "noopener,noreferrer"]]);
  await pending;
});
