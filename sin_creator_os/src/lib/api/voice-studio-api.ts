import { AuthApi } from "@/lib/api/auth-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface VoiceStudioAsset {
  id: string;
  mime_detected: string;
  duration_ms: number;
  original_filename: string;
  url: string;
}

export interface VoiceProfile {
  id: string;
  name: string;
  provider: "GWEN_TTS" | "VIE_NEU_V3_TURBO";
  reference_filename?: string | null;
  duration_ms?: number | null;
  created_at?: string | null;
}

export interface TTSAdvancedSettings {
  temperature?: number;
  top_k?: number;
  top_p?: number;
  repetition_penalty?: number;
  denoise_reference?: boolean;
  use_reference_codes?: boolean;
  max_new_frames?: number;
  max_chars?: number;
  max_new_tokens?: number;
  x_vector_only_mode?: boolean;
}

export interface VoiceStudioJob {
  job_id: string;
  state: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  provider: string;
  model_id: string;
  error_code?: string | null;
  error_message?: string | null;
  asset?: VoiceStudioAsset | null;
  created_at?: string | null;
  playback_url?: string;
}

export interface CreateVoiceStudioJob {
  provider: "GWEN_TTS" | "VIE_NEU_V3_TURBO";
  text: string;
  voice_id?: string;
  voice_profile_id?: string;
  reference_asset_id?: string;
  reference_text?: string;
  voice_clone_consent: boolean;
  pronunciation_dictionary: string;
  advanced: TTSAdvancedSettings;
  idempotency_key: string;
}

export interface CreateVoiceProfile {
  name: string;
  provider: VoiceProfile["provider"];
  reference_asset_id: string;
  reference_text?: string;
  voice_clone_consent: true;
}

export interface VoiceStudioSettings {
  pronunciation_dictionary: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/v1/voice-studio${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-Id": AuthApi.getWorkspaceId(),
      Authorization: `Bearer ${AuthApi.getAuthToken()}`,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    throw new Error(typeof detail === "object" ? detail.message || detail.error_code : detail || `Lỗi API ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

function formatJob(job: VoiceStudioJob): VoiceStudioJob {
  if (job.asset?.url.startsWith("/")) {
    job.asset.url = `${API_BASE_URL}${job.asset.url}`;
  }
  return job;
}

export const voiceStudioApi = {
  getSettings() {
    return request<VoiceStudioSettings>("/settings");
  },
  saveSettings(payload: VoiceStudioSettings) {
    return request<VoiceStudioSettings>("/settings", { method: "PUT", body: JSON.stringify(payload) });
  },
  createJob(payload: CreateVoiceStudioJob) {
    return request<VoiceStudioJob>("/jobs", { method: "POST", body: JSON.stringify(payload) }).then(formatJob);
  },
  getJob(jobId: string) {
    return request<VoiceStudioJob>(`/jobs/${encodeURIComponent(jobId)}`).then(formatJob);
  },
  listJobs() {
    return request<VoiceStudioJob[]>("/jobs?limit=20").then((jobs) => jobs.map(formatJob));
  },
  listVoices() {
    return request<VoiceProfile[]>("/voices");
  },
  createVoice(payload: CreateVoiceProfile) {
    return request<VoiceProfile>("/voices", { method: "POST", body: JSON.stringify(payload) });
  },
};
