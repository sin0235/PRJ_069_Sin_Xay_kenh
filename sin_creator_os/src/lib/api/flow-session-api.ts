import { AuthApi } from "@/lib/api/auth-api";
import { getApiBaseUrl } from "@/lib/api/base-url";
import { FlowSessionApiError, parseFlowApiError } from "@/lib/api/flow-session-errors";
export { FlowSessionApiError, parseFlowApiError } from "@/lib/api/flow-session-errors";
export type { ParsedFlowApiError } from "@/lib/api/flow-session-errors";

export type FlowProviderState = "READY" | "LOGIN_REQUIRED" | "QUOTA_LIMITED" | "UNKNOWN" | "CHECK_FAILED";
export type FlowCommandState = "PENDING" | "RUNNING" | "DONE" | "FAILED";
export type FlowLoginSessionState =
  | "LOGIN_REQUESTED"
  | "OPENING"
  | "OPEN"
  | "CLOSE_REQUESTED"
  | "CLOSED"
  | "TIMED_OUT"
  | "FAILED"
  | "INTERRUPTED";

export interface FlowProfile {
  id: string;
  name: string;
  is_active: boolean;
  state: FlowProviderState;
  flow_music_state: FlowProviderState;
  google_flow_state: FlowProviderState;
  last_checked_at: string | null;
  error_code: string | null;
}

export interface FlowSessionCommand {
  id: string;
  profile_id: string;
  session_id: string | null;
  kind: "LOGIN" | "CHECK" | "CLOSE";
  state: FlowCommandState;
  result: Record<string, unknown> | null;
  error_code: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface FlowLoginSession {
  id: string;
  profile_id: string;
  status: FlowLoginSessionState;
  error_code: string | null;
  expires_at: string;
  started_at: string | null;
  closed_at: string | null;
}

export interface FlowDesktopAccess {
  url: string;
  expires_at: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(AuthApi.getAuthHeaders());
  headers.set("Accept", "application/json");
  if (init.body === undefined) headers.delete("Content-Type");
  for (const [key, value] of new Headers(init.headers)) headers.set(key, value);

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const parsed = parseFlowApiError(body, `Flow request failed (${response.status}).`);
    throw new FlowSessionApiError(parsed.errorCode, parsed.message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const jsonBody = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const flowSessionApi = {
  listProfiles(): Promise<FlowProfile[]> {
    return request("/v1/media/flow/profiles");
  },

  currentProfile(): Promise<FlowProfile> {
    return request("/v1/media/flow/profiles/current");
  },

  createProfile(name: string): Promise<FlowProfile> {
    return request("/v1/media/flow/profiles", jsonBody({ name }));
  },

  activateProfile(profileId: string): Promise<FlowProfile> {
    return request(`/v1/media/flow/profiles/${encodeURIComponent(profileId)}/activate`, jsonBody({}));
  },

  checkProfile(profileId?: string | null): Promise<FlowSessionCommand> {
    const path = profileId
      ? `/v1/media/flow/profiles/${encodeURIComponent(profileId)}/check`
      : "/v1/media/flow/profiles/check";
    return request(path, jsonBody(profileId ? {} : { profile_id: null }));
  },

  getCommand(commandId: string): Promise<FlowSessionCommand> {
    return request(`/v1/media/flow/commands/${encodeURIComponent(commandId)}`);
  },

  startLoginSession(profileId?: string | null): Promise<FlowLoginSession> {
    return request("/v1/media/flow/login-sessions/start", jsonBody({ profile_id: profileId || null }));
  },

  getLoginSession(sessionId: string): Promise<FlowLoginSession> {
    return request(`/v1/media/flow/login-sessions/${encodeURIComponent(sessionId)}`);
  },

  currentLoginSession(): Promise<FlowLoginSession | null> {
    return request("/v1/media/flow/login-sessions/current");
  },

  closeLoginSession(sessionId: string): Promise<FlowLoginSession> {
    return request(`/v1/media/flow/login-sessions/${encodeURIComponent(sessionId)}/close`, jsonBody({}));
  },

  async createDesktopAccess(sessionId: string): Promise<FlowDesktopAccess> {
    const access = await request<FlowDesktopAccess>(
      `/v1/media/flow/login-sessions/${encodeURIComponent(sessionId)}/desktop-access`,
      jsonBody({}),
    );
    return {
      ...access,
      url: new URL(access.url, getApiBaseUrl() || window.location.origin).toString(),
    };
  },
};
