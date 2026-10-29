import assert from "node:assert/strict";
import { test } from "node:test";
import { FlowSessionApiError, parseFlowApiError } from "../../src/lib/api/flow-session-errors.ts";

test("Flow API errors preserve the canonical error_code and safe message", () => {
  assert.deepEqual(
    parseFlowApiError(
      {
        error_code: "FLOW_QUOTA_LIMITED",
        message_safe: "This Flow account has no available quota.",
        detail: { error_code: "FLOW_QUOTA_LIMITED", message: "This Flow account has no available quota." },
      },
      "Fallback",
    ),
    { errorCode: "FLOW_QUOTA_LIMITED", message: "This Flow account has no available quota." },
  );
  assert.deepEqual(
    parseFlowApiError({ detail: { error_code: "FLOW_SESSION_BUSY", message: "A session is already open." } }, "Fallback"),
    { errorCode: "FLOW_SESSION_BUSY", message: "A session is already open." },
  );
  const failure = new FlowSessionApiError("FLOW_SESSION_BUSY", "A session is already open.", 409);
  assert.equal(failure.errorCode, "FLOW_SESSION_BUSY");
  assert.equal(failure.status, 409);
  assert.equal(failure.message, "A session is already open.");
});
