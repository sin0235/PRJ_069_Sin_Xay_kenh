import { AuthApi } from "@/lib/api/auth-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export class ContentVideoApiError extends Error {
  constructor(message: string, readonly code?: string) {
    super(message);
    this.name = "ContentVideoApiError";
  }
}

export interface ContentVideoPlan {
  id: string;
  project_id: string;
  revision: number;
  status: string;
  source_content: string;
  target_duration_seconds: number;
  style_snapshot: { style_name: string; visual_rules: string; palette: string[] };
  storyboard: { title: string; narration: string; shots: { shot_id: string; scene: string; narration: string; prompt: string; negative_prompt: string; duration_seconds: number }[] };
  llm_model: string;
}

export interface ContentVideoRun {
  id: string;
  voice_asset_id?: string | null;
  status: string;
  current_step?: string | null;
  steps: { shot_id: string; state: string; asset_id?: string | null }[];
  final_asset_id?: string | null;
  qc_report?: { status: string; acceptance_mode?: string; voice_source?: string; issues: string[]; measured?: Record<string, unknown>; export_asset_id?: string; speech_alignment?: string } | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string;
  started_at?: string | null;
}

async function request<T>(projectId: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/v1/media/projects/${encodeURIComponent(projectId)}/content-video${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-Id": AuthApi.getWorkspaceId(),
      Authorization: `Bearer ${AuthApi.getAuthToken()}`,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ContentVideoApiError(
      typeof detail === "string" ? detail : detail?.message || `Yêu cầu thất bại (${response.status}).`,
      typeof detail === "object" ? detail?.error_code : undefined,
    );
  }
  return response.json();
}

export const contentVideoApi = {
  createPlan: (projectId: string, content: string, duration: number) => request<ContentVideoPlan>(projectId, "/plans", {
    method: "POST",
    body: JSON.stringify({ content, target_duration_seconds: duration }),
  }),
  getPlan: (projectId: string, planId: string) => request<ContentVideoPlan>(projectId, `/plans/${encodeURIComponent(planId)}`),
  approvePlan: (projectId: string, planId: string) => request<ContentVideoPlan>(projectId, `/plans/${encodeURIComponent(planId)}/approve`, { method: "POST" }),
  createRun: (projectId: string, planId: string, voiceAssetId: string | null, idempotencyKey: string) => request<ContentVideoRun>(projectId, "/runs", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId, voice_asset_id: voiceAssetId, idempotency_key: idempotencyKey }),
  }),
  getRun: (projectId: string, runId: string) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}`),
  resumeRun: (projectId: string, runId: string) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}/resume`, { method: "POST" }),
  reconcileShot: (projectId: string, runId: string, shotId: string, assetId: string, reason: string) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}/reconcile`, {
    method: "POST",
    body: JSON.stringify({ shot_id: shotId, asset_id: assetId, reason }),
  }),
};
