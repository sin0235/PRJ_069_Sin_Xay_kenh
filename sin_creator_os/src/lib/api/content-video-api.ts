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
  style_snapshot: { style_name: string; visual_rules: string; palette: string[]; aspect_ratio: "9:16" | "16:9" };
  storyboard: { title: string; narration: string; shots: { shot_id: string; scene: string; narration: string; prompt: string; negative_prompt: string; duration_seconds: number }[] };
  llm_model: string;
}

export interface ContentVideoRun {
  id: string;
  voice_asset_id?: string | null;
  voice_source?: "NONE" | "UPLOAD" | "TTS";
  tts_provider?: "GWEN_TTS" | "VIE_NEU_V3_TURBO" | null;
  include_subtitles?: boolean;
  status: string;
  current_step?: string | null;
  steps: { shot_id: string; state: string; asset_id?: string | null; flow_project_url?: string | null }[];
  final_asset_id?: string | null;
  qc_report?: { status: string; acceptance_mode?: string; voice_source?: string; flow_native_audio?: boolean; issues: string[]; measured?: Record<string, unknown>; export_asset_id?: string; speech_alignment?: string } | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string;
  started_at?: string | null;
}

export interface ContentVideoHistory {
  plan: ContentVideoPlan | null;
  run: ContentVideoRun | null;
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
  getLatestHistory: (projectId: string) => request<ContentVideoHistory>(projectId, "/history"),
  createPlan: (projectId: string, content: string, duration: number, aspectRatio: "9:16" | "16:9") => request<ContentVideoPlan>(projectId, "/plans", {
    method: "POST",
    body: JSON.stringify({ content, target_duration_seconds: duration, aspect_ratio: aspectRatio }),
  }),
  getPlan: (projectId: string, planId: string) => request<ContentVideoPlan>(projectId, `/plans/${encodeURIComponent(planId)}`),
  updatePlan: (projectId: string, planId: string, storyboard: ContentVideoPlan["storyboard"]) => request<ContentVideoPlan>(projectId, `/plans/${encodeURIComponent(planId)}`, {
    method: "PUT",
    body: JSON.stringify({ storyboard }),
  }),
  approvePlan: (projectId: string, planId: string) => request<ContentVideoPlan>(projectId, `/plans/${encodeURIComponent(planId)}/approve`, { method: "POST" }),
  createRun: (projectId: string, planId: string, voice: { source: "NONE" | "UPLOAD" | "TTS"; assetId?: string | null; provider?: "GWEN_TTS" | "VIE_NEU_V3_TURBO"; voiceId?: string; referenceAssetId?: string; referenceText?: string; consent?: boolean; includeSubtitles?: boolean }, idempotencyKey: string) => request<ContentVideoRun>(projectId, "/runs", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId, voice_source: voice.source, voice_asset_id: voice.source === "UPLOAD" ? voice.assetId : null, tts_provider: voice.source === "TTS" ? voice.provider : null, tts_voice_id: voice.source === "TTS" ? voice.voiceId : null, tts_reference_asset_id: voice.source === "TTS" ? voice.referenceAssetId : null, tts_reference_text: voice.source === "TTS" ? voice.referenceText : null, voice_clone_consent: voice.source === "TTS" && !!voice.consent, include_subtitles: voice.includeSubtitles ?? true, idempotency_key: idempotencyKey }),
  }),
  retryRun: (projectId: string, runId: string, options: { shotIds: string[]; newFlowProject?: boolean; confirmNoFlowClip?: boolean; idempotencyKey: string }) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}/retry`, {
    method: "POST",
    body: JSON.stringify({ shot_ids: options.shotIds, new_flow_project: !!options.newFlowProject, confirm_no_flow_clip: !!options.confirmNoFlowClip, idempotency_key: options.idempotencyKey }),
  }),
  getRun: (projectId: string, runId: string) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}`),
  resumeRun: (projectId: string, runId: string) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}/resume`, { method: "POST" }),
  reconcileShot: (projectId: string, runId: string, shotId: string, assetId: string, reason: string) => request<ContentVideoRun>(projectId, `/runs/${encodeURIComponent(runId)}/reconcile`, {
    method: "POST",
    body: JSON.stringify({ shot_id: shotId, asset_id: assetId, reason }),
  }),
};
