// Client Service giao tiếp với Backend Media Studio API (PRJ_069)
// Tích hợp Flow Music Plus, Google Flow 9:16 và FFmpeg Auto-Ducking
import { AuthApi } from "@/lib/api/auth-api";
import { getApiBaseUrl } from "@/lib/api/base-url";
import { randomUuid } from "@/lib/utils";

const API_BASE_URL = getApiBaseUrl();

function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, credentials: "include" });
}

function mediaAuthHeaders(
  workspaceId = AuthApi.getWorkspaceId(),
  token?: string,
  contentType?: string,
): Record<string, string> {
  const headers = { ...AuthApi.getAuthHeaders() };
  delete headers["Content-Type"];

  if (workspaceId.trim()) headers["X-Workspace-Id"] = workspaceId.trim();
  else delete headers["X-Workspace-Id"];

  const explicitToken = token?.trim();
  if (explicitToken) headers.Authorization = `Bearer ${explicitToken}`;
  else if (!headers.Authorization?.trim() || headers.Authorization.trim() === "Bearer") {
    delete headers.Authorization;
  }

  if (contentType) headers["Content-Type"] = contentType;
  return headers;
}

function apiErrorMessage(value: unknown, fallback: string): string {
  const body = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const detail = body.detail;
  const nested = detail && typeof detail === "object" ? detail as Record<string, unknown> : {};
  for (const message of [body.message_safe, nested.message, nested.error_message, nested.error_code, detail, body.error_message, body.error_code]) {
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

async function responseErrorMessage(res: Response, fallback: string): Promise<string> {
  return apiErrorMessage(await res.json().catch(() => null), fallback);
}

interface MediaJobStatusResponse {
  state: string;
  output_asset_ids?: string[];
  asset?: MediaAssetResponse | null;
  error_code?: string | null;
  error_message?: string | null;
}

interface AsyncMediaJobResponse {
  job_id: string;
  state: string;
}

export interface AutoEditJobStatus {
  state: string;
  output_asset_ids?: string[];
  error_code?: string | null;
  error_message?: string | null;
}

function mediaJobError(job: MediaJobStatusResponse, jobId?: string): Error & {
  jobId?: string;
  canResume?: boolean;
  resumeUrl?: string;
  errorCode?: string;
} {
  const message = job.error_message || job.error_code || "Tác vụ tạo media không hoàn tất.";
  const error = new Error(job.error_code && job.error_message && !job.error_message.includes(job.error_code)
    ? `${message} (${job.error_code})`
    : message) as Error & { jobId?: string; canResume?: boolean; resumeUrl?: string; errorCode?: string };
  error.jobId = jobId;
  error.errorCode = job.error_code ?? undefined;
  error.canResume = job.state === "BLOCKED_FLOW_LOGIN"
    || job.state === "BLOCKED_FLOW_QUOTA"
    || job.state === "BLOCKED_FLOW_SETUP";
  if (error.canResume) error.resumeUrl = "/flow-sessions";
  return error;
}

async function waitForMediaAsset(jobId: string, headers: Record<string, string>): Promise<MediaAssetResponse> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 10 * 60 * 1000) {
    const res = await apiFetch(`${API_BASE_URL}/v1/ai-jobs/${encodeURIComponent(jobId)}`, { headers });
    if (!res.ok) {
      throw new Error(await responseErrorMessage(res, `Không thể kiểm tra trạng thái tác vụ (${res.status}).`));
    }
    const job: MediaJobStatusResponse = await res.json();
    if (job.state === "SUCCEEDED") {
      if (job.asset) return formatAsset(job.asset);
      const assetId = job.output_asset_ids?.[0];
      if (!assetId) throw new Error("Tác vụ đã hoàn tất nhưng không có mã tệp media.");
      const assetRes = await apiFetch(`${API_BASE_URL}/v1/media/assets/${encodeURIComponent(assetId)}`, { headers });
      if (!assetRes.ok) {
        throw new Error(await responseErrorMessage(assetRes, `Không thể tải tệp media (${assetRes.status}).`));
      }
      return formatAsset(await assetRes.json());
    }
    if (["FAILED", "NEEDS_RECONCILIATION", "BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_QUOTA", "BLOCKED_FLOW_SETUP", "CANCELLED", "EXPIRED"].includes(job.state)) {
      throw mediaJobError(job, jobId);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error("Tác vụ vẫn đang được xử lý; hãy kiểm tra lại thư viện media sau.");
}

function formatAsset(asset: MediaAssetResponse): MediaAssetResponse {
  if (asset && asset.url && asset.url.startsWith("/")) {
    asset.url = `${API_BASE_URL}${asset.url}`;
  }
  return asset;
}

async function fetchAssetBlob(url: string): Promise<Blob> {
  const res = await apiFetch(url, {
    headers: mediaAuthHeaders(),
  });
  if (!res.ok) throw new Error(await responseErrorMessage(res, `Không thể tải tệp media (${res.status}).`));
  return res.blob();
}

export interface MediaAssetResponse {
  id: string;
  workspace_id: string;
  project_id?: string;
  storage_key: string;
  sha256: string;
  byte_size: number;
  mime_detected: string;
  duration_ms?: number;
  source_product: string;
  original_filename?: string;
  parent_asset_id?: string | null;
  approval_state: string;
  url?: string;
  created_at: string;
}

export interface ProductionProjectResponse {
  id: string;
  workspace_id: string;
  title: string;
  workflow_type: "AI_VIDEO" | "AUTO_EDIT";
  status: string;
  created_at: string;
}

export type ProductionWorkflowType = ProductionProjectResponse["workflow_type"];

export interface TimelineClip {
  clip_id: string;
  asset_id: string;
  media_type: "image" | "video";
  start_ms: number;
  duration_ms: number;
  trim_in_ms?: number;
  trim_out_ms?: number;
  fit?: "cover" | "contain";
}

export interface TimelineAudioTrack {
  asset_id: string;
  start_ms: number;
  duration_ms?: number;
  gain_db?: number;
  ducking_attenuation_db?: number;
}

export interface TimelineCaption {
  caption_id?: string;
  text: string;
  start_ms: number;
  duration_ms: number;
  font_size?: number;
  safe_zone?: boolean;
  visual_type?: "callout";
  position_y_px?: number;
}

export interface TimelineOverlay {
  asset_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  start_ms: number;
  duration_ms: number;
}

export interface TimelineDocument {
  width?: number;
  height?: number;
  fps?: number;
  clips: TimelineClip[];
  voice_track?: TimelineAudioTrack | null;
  music_track?: TimelineAudioTrack | null;
  captions?: TimelineCaption[];
  overlays?: TimelineOverlay[];
  caption_style?: "legacy" | "vietsub_v1" | "vietsub_karaoke_v2";
  transition_seconds?: number;
}

export interface TimelineVersionResponse {
  id: string;
  project_id: string;
  version: number;
  timeline: TimelineDocument;
  is_locked: boolean;
  created_by: string;
  created_at: string;
}

export interface UploadAssetParams {
  file: File;
  project_id?: string;
  expected_category?: "audio" | "image" | "video";
  source_product?: string;
  workspace_id?: string;
  token?: string;
  onProgress?: (loadedBytes: number, totalBytes: number) => void;
}

export interface UploadVideoInChunksParams {
  file: File;
  project_id: string;
  resume_session_id?: string;
  workspace_id?: string;
  token?: string;
  onProgress?: (loadedBytes: number, totalBytes: number) => void;
  onSessionId?: (sessionId: string) => void;
}

function getVideoUploadStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export interface CompiledVideoPromptResponse {

  raw_prompt: string;
  compiled_directive: string;
  shot_type: string;
  camera_movement: string;
  lighting_atmosphere: string;
  kinetic_action: string;
  retention_hook_3s: string;
  suggested_audio_sfx: string;
  aspect_ratio: string;
  target_duration_seconds: number;
  model_target: string;
  creator_guidelines: string[];
}

export interface MusicCapabilityItem {
  provider: string;
  mode: string;
  model_id: string;
  enabled: boolean;
  blocked_reason?: string | null;
  max_duration_sec: number;
  cost_per_generation_usd: number;
  requires_approval: boolean;
  observed_at: string;
}

export interface MusicCapabilitiesResponse {
  workspace_id: string;
  items: MusicCapabilityItem[];
  default_provider: string;
  pilot_enabled: boolean;
}

export interface GenerateMusicParams {
  prompt: string;
  genre?: string;
  mood?: string;
  lyrics?: string;
  use_official_lyria?: boolean;
  provider?: "GOOGLE_OFFICIAL" | "FLOW_BROWSER_PILOT" | "LOCAL_TEST_SYNTH";
  mode?: "CLIP_30S" | "FULL_SONG" | "PILOT_ASSISTED" | "SYNTH_FIXTURE";
  duration_sec?: number;
  project_id?: string;
  idempotency_key?: string;
  normalize_tiktok?: boolean;
  workspace_id?: string;
  token?: string;
}

interface MusicJobStatusResponse {
  job_id?: string;
  state: string;
  error_code?: string | null;
  error_message?: string | null;
  asset?: MediaAssetResponse | null;
}

export interface MixAudioParams {
  voice_asset_id: string;
  music_asset_id: string;
  music_attenuation_db?: number;
  workspace_id?: string;
  token?: string;
}

export interface GenerateVideoParams {
  prompt: string;
  start_image_asset_id?: string;
  aspect_ratio?: string;
  use_official_omni?: boolean;
  remove_watermark?: boolean;
  project_id?: string;
  idempotency_key?: string;
  workspace_id?: string;
  token?: string;
}

export interface AssembleVideoParams {
  scene_asset_ids: string[];
  audio_asset_id: string;
  workspace_id?: string;
  token?: string;
}

export const mediaStudioApi = {
  async listProjects(workflowType: ProductionWorkflowType = "AI_VIDEO"): Promise<ProductionProjectResponse[]> {
    const res = await apiFetch(`${API_BASE_URL}/v1/media/projects?workflow_type=${workflowType}`, {
      headers: mediaAuthHeaders(),
    });
    if (!res.ok) throw new Error(`Không thể tải dự án (${res.status}).`);
    return res.json();
  },

  async createProject(title: string, workflowType: ProductionWorkflowType = "AI_VIDEO"): Promise<ProductionProjectResponse> {
    const res = await apiFetch(`${API_BASE_URL}/v1/media/projects`, {
      method: "POST",
      headers: mediaAuthHeaders(undefined, undefined, "application/json"),
      body: JSON.stringify({ title, workflow_type: workflowType }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Không thể tạo dự án (${res.status}).`);
    }
    return res.json();
  },

  async openGoogleFlowLogin(): Promise<void> {
    if (typeof window === "undefined") return;
    window.open("/flow-sessions", "_blank", "noopener,noreferrer");
  },

  async resumeAiJob(
    jobId: string,
    opts: { profile_id?: string; workspace_id?: string; token?: string } = {},
  ): Promise<MediaAssetResponse> {
    const query = opts.profile_id ? `?profile_id=${encodeURIComponent(opts.profile_id)}` : "";
    const selectedWorkspace = opts.workspace_id?.trim() ? opts.workspace_id : AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(selectedWorkspace, opts.token);
    const res = await apiFetch(`${API_BASE_URL}/v1/ai-jobs/${encodeURIComponent(jobId)}/resume${query}`, {
      method: "POST",
      headers,
    });
    const data: AsyncMediaJobResponse = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(apiErrorMessage(data, `Không thể tiếp tục tác vụ (${res.status}).`));
    if (data.job_id) return waitForMediaAsset(data.job_id, headers);
    throw new Error("Máy chủ không trả mã tác vụ để tiếp tục.");
  },

  async getMusicCapabilities(): Promise<MusicCapabilitiesResponse> {
    const res = await apiFetch(`${API_BASE_URL}/v1/media/music/capabilities`, {
      method: "GET",
      headers: mediaAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message_safe || err.detail?.message || err.detail || `Không thể kiểm tra năng lực âm nhạc (${res.status}).`);
    }
    return res.json();
  },

  async reviewAsset(assetId: string, decision: "APPROVE" | "REJECT", reviewNotes?: string): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("decision", decision);
    if (reviewNotes) formData.append("review_notes", reviewNotes);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/assets/${assetId}/review`, {
      method: "POST",
      headers: mediaAuthHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message_safe || err.detail?.message || err.detail || `Lỗi phê duyệt tư liệu (${res.status}).`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  // 1. Sinh bài hát qua Flow Music Plus (Flow Music) hoặc Lyria
  async generateMusic(params: GenerateMusicParams): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("prompt", params.prompt);
    formData.append("genre", params.genre || "Pop");
    formData.append("mood", params.mood || "Upbeat");
    if (params.lyrics) formData.append("lyrics", params.lyrics);
    formData.append("use_official_lyria", String(!!params.use_official_lyria));
    if (params.provider) formData.append("provider", params.provider);
    if (params.mode) formData.append("mode", params.mode);
    if (params.duration_sec) formData.append("duration_sec", String(params.duration_sec));
    if (params.project_id) formData.append("project_id", params.project_id);
    const idempotencyKey = params.idempotency_key || randomUuid();
    formData.append("idempotency_key", idempotencyKey);
    formData.append("normalize_tiktok", String(params.normalize_tiktok !== false));

    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId, params.token);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/music/generate`, {
      method: "POST",
      headers,
      body: formData,
    });

    const data: MediaAssetResponse | AsyncMediaJobResponse = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(apiErrorMessage(data, `Lỗi tạo nhạc: ${res.statusText}`));
    if ("job_id" in data && data.job_id) return waitForMediaAsset(data.job_id, headers);
    if ("id" in data && data.id) return formatAsset(data);
    throw new Error("Máy chủ không trả mã tác vụ hoặc tệp nhạc.");
  },

  async waitForMusicResult(idempotencyKey: string, signal: AbortSignal): Promise<MediaAssetResponse> {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 10 * 60 * 1000) {
      try {
        const res = await apiFetch(`${API_BASE_URL}/v1/media/music/jobs/${encodeURIComponent(idempotencyKey)}`, {
          headers: mediaAuthHeaders(),
          signal,
        });
        if (res.status === 404) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          continue;
        }
        if (!res.ok) throw new Error(await responseErrorMessage(res, `Không thể kiểm tra trạng thái tạo nhạc (${res.status}).`));

        const job: MusicJobStatusResponse = await res.json();
        if (job.state === "SUCCEEDED") {
          if (!job.asset) throw new Error("Tác vụ đã hoàn tất nhưng không tìm thấy tệp nhạc đã lưu.");
          return formatAsset(job.asset);
        }
        if (["FAILED", "NEEDS_RECONCILIATION", "BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_QUOTA", "BLOCKED_FLOW_SETUP", "CANCELLED", "EXPIRED"].includes(job.state)) {
          throw mediaJobError(job, job.job_id);
        }
      } catch (error) {
        if (signal.aborted || error instanceof Error && error.message !== "Failed to fetch") throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    throw new Error("Flow vẫn đang xử lý. Tác vụ được giữ lại; hãy kiểm tra thư viện tư liệu để lấy kết quả khi hoàn tất.");
  },

  // 2. Hòa âm tự động hạ nhạc nền (Auto-ducking)
  async mixAudio(params: MixAudioParams): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("voice_asset_id", params.voice_asset_id);
    formData.append("music_asset_id", params.music_asset_id);
    formData.append("music_attenuation_db", String(params.music_attenuation_db ?? -18.0));

    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId, params.token);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/audio/mix`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi hòa âm: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  // 3. Sinh video phân cảnh dọc 9:16 qua Google Flow (Flow Music) hoặc Gemini Omni
  
  // 3a. Biên dịch bộ lệnh video đa tầng & hướng dẫn chi tiết từ yêu cầu người dùng
  async compileVideoPrompt(params: { prompt: string; aspect_ratio?: string; duration_seconds?: number }): Promise<CompiledVideoPromptResponse> {
    const formData = new FormData();
    formData.append("prompt", params.prompt);
    formData.append("aspect_ratio", params.aspect_ratio || "16:9");
    formData.append("duration_seconds", String(params.duration_seconds || 10));

    const wsId = AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/video/prompt/compile`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi biên dịch lệnh: ${res.statusText}`);
    }
    return await res.json();
  },

  async generateVideo(params: GenerateVideoParams): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("prompt", params.prompt);
    formData.append("aspect_ratio", params.aspect_ratio || "9:16");
    formData.append("use_official_omni", String(!!params.use_official_omni));
    if (params.start_image_asset_id) formData.append("start_image_asset_id", params.start_image_asset_id);
    formData.append("remove_watermark", String(params.remove_watermark === true));
    if (params.project_id) formData.append("project_id", params.project_id);
    const idempotencyKey = params.idempotency_key || randomUuid();
    formData.append("idempotency_key", idempotencyKey);

    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId, params.token);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/video/generate`, {
      method: "POST",
      headers,
      body: formData,
    });

    const data: MediaAssetResponse | AsyncMediaJobResponse = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(apiErrorMessage(data, `Lỗi tạo video: ${res.statusText}`));
    if ("job_id" in data && data.job_id) return waitForMediaAsset(data.job_id, headers);
    if ("id" in data && data.id) return formatAsset(data);
    throw new Error("Máy chủ không trả mã tác vụ hoặc tệp video.");
  },

  // 3b. Mo rong video 16:9 (Omni 10s hoac tai len) sang 9:16 chuan TikTok
  async expandVideo(params: { file?: File; asset_id?: string; project_id?: string; blur_strength?: number; remove_watermark?: boolean }): Promise<MediaAssetResponse> {
    const formData = new FormData();
    if (params.file) formData.append("file", params.file);
    if (params.asset_id) formData.append("asset_id", params.asset_id);
    if (params.project_id) formData.append("project_id", params.project_id);
    formData.append("blur_strength", String(params.blur_strength ?? 25));
    formData.append("remove_watermark", String(params.remove_watermark !== false));

    const wsId = AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/video/expand`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Loi mo rong video: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },


  // 3c. Khử logo / watermark Google Veo & Gemini AI khỏi video (Reverse Alpha Blending v0.6.5)
  async removeWatermark(params: { file?: File; asset_id?: string }): Promise<MediaAssetResponse> {
    const formData = new FormData();
    if (params.file) formData.append("file", params.file);
    if (params.asset_id) formData.append("asset_id", params.asset_id);
    formData.append("use_cpu", "true");

    const wsId = AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/video/remove-watermark`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi khử watermark: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  // 4. Ghép nối video phân cảnh và audio thành video hoàn chỉnh TikTok
  async assembleVideo(params: AssembleVideoParams): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("scene_asset_ids_json", JSON.stringify(params.scene_asset_ids));
    formData.append("audio_asset_id", params.audio_asset_id);

    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId, params.token);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/video/assemble`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi ghép video: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  // 5. Lấy danh sách tài sản truyền thông thực tế từ Backend
  async createAssetObjectUrl(url: string): Promise<string> {
    return URL.createObjectURL(await fetchAssetBlob(url));
  },

  async getAssetText(url: string): Promise<string> {
    return fetchAssetBlob(url).then((blob) => blob.text());
  },

  async downloadAsset(url: string, filename: string): Promise<void> {
    const objectUrl = URL.createObjectURL(await fetchAssetBlob(url));
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  },

  async listAssets(opts: string | { workspace_id?: string; project_id?: string; token?: string; limit?: number; throwOnError?: boolean } = "default_ws", token?: string): Promise<MediaAssetResponse[]> {
    const wsId = typeof opts === "string" ? opts : (opts.workspace_id || AuthApi.getWorkspaceId());
    const tok = typeof opts === "string" ? token : opts.token;
    const headers = mediaAuthHeaders(wsId, tok);
    const projectId = typeof opts === "string" ? undefined : opts.project_id;
    const limit = typeof opts === "string" || opts.limit === undefined ? "" : `&limit=${opts.limit}`;
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}${limit}` : "";

    const res = await apiFetch(`${API_BASE_URL}/v1/media/assets${query}`, {
      headers,
    });

    if (!res.ok) {
      if (typeof opts !== "string" && opts.throwOnError) {
        throw new Error(await responseErrorMessage(res, `Không thể tải danh sách tư liệu (${res.status}).`));
      }
      return [];
    }
    const data = await res.json();
    return Array.isArray(data) ? data.map(formatAsset) : [];
  },

  async getAsset(assetId: string): Promise<MediaAssetResponse> {
    const res = await apiFetch(`${API_BASE_URL}/v1/media/assets/${encodeURIComponent(assetId)}`, {
      headers: mediaAuthHeaders(),
    });
    if (!res.ok) throw new Error(await responseErrorMessage(res, `Không thể tải tệp media (${res.status}).`));
    return formatAsset(await res.json());
  },

  async startAutoEditVideo(projectId: string, sourceAssetId: string): Promise<{ job_id: string; state: string }> {
    const res = await apiFetch(`${API_BASE_URL}/v1/media/projects/${encodeURIComponent(projectId)}/dung/tu-dong-dung-video-dai`, {
      method: "POST",
      headers: mediaAuthHeaders(undefined, undefined, "application/json"),
      body: JSON.stringify({ source_asset_id: sourceAssetId, idempotency_key: `auto-edit-${randomUuid()}` }),
    });
    if (!res.ok) throw new Error(await responseErrorMessage(res, `Không thể tạo yêu cầu dựng video (${res.status}).`));
    return res.json();
  },

  async getAutoEditJob(jobId: string): Promise<AutoEditJobStatus> {
    const res = await apiFetch(`${API_BASE_URL}/v1/ai-jobs/${encodeURIComponent(jobId)}`, {
      headers: mediaAuthHeaders(),
    });
    if (!res.ok) throw new Error(await responseErrorMessage(res, `Không thể kiểm tra tác vụ (${res.status}).`));
    return res.json();
  },

  // 6. Tải lên tệp tư liệu (ảnh, video, audio)
  async uploadAsset(params: UploadAssetParams): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.project_id) formData.append("project_id", params.project_id);
    formData.append("expected_category", params.expected_category || "video");
    formData.append("source_product", params.source_product || "UPLOAD");

    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers = mediaAuthHeaders(wsId, params.token);

    const res = await apiFetch(`${API_BASE_URL}/v1/media/upload`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi tải lên tệp: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  async uploadVideoInChunks(params: UploadVideoInChunksParams): Promise<MediaAssetResponse> {
    const headers = mediaAuthHeaders(params.workspace_id, params.token);
    const storage = getVideoUploadStorage();
    const sessionKey = `prj069:auto-edit-upload:${encodeURIComponent(params.workspace_id || AuthApi.getWorkspaceId())}:${encodeURIComponent(params.project_id)}:${params.file.size}:${params.file.lastModified}:${encodeURIComponent(params.file.name)}`;
    type UploadSession = { session_id: string; next_offset: number; byte_size: number; chunk_size: number; project_id?: string };
    let session: UploadSession | null = null;
    let resumeSessionId = params.resume_session_id;
    try {
      resumeSessionId ||= storage?.getItem(sessionKey) || undefined;
    } catch {
      // Storage can be disabled; the upload still works for the current page.
    }

    if (resumeSessionId) {
      const res = await apiFetch(`${API_BASE_URL}/v1/media/upload-sessions/${encodeURIComponent(resumeSessionId)}`, { headers });
      if (res.ok) {
        const resumed = await res.json() as UploadSession;
        if (resumed.byte_size !== params.file.size || resumed.project_id !== params.project_id) {
          throw new Error("Phiên tải trước không khớp video hoặc dự án đang chọn.");
        }
        session = resumed;
      } else if (res.status !== 404 && res.status !== 410) {
        throw new Error(await responseErrorMessage(res, "Không thể tiếp tục phiên tải video."));
      }
    }
    if (!session) {
      const res = await apiFetch(`${API_BASE_URL}/v1/media/upload-sessions`, {
        method: "POST",
        headers: mediaAuthHeaders(params.workspace_id, params.token, "application/json"),
        body: JSON.stringify({ filename: params.file.name, byte_size: params.file.size, project_id: params.project_id }),
      });
      if (!res.ok) throw new Error(await responseErrorMessage(res, "Không thể tạo phiên tải video."));
      session = await res.json() as UploadSession;
    }
    const uploadSession = session;
    if (!uploadSession) throw new Error("Máy chủ không trả về phiên tải video.");
    params.onSessionId?.(uploadSession.session_id);
    try {
      storage?.setItem(sessionKey, uploadSession.session_id);
    } catch {
      // The server session remains resumable from the current page.
    }

    const chunkSize = Math.min(uploadSession.chunk_size, 64 * 1024 * 1024);
    if (!Number.isSafeInteger(chunkSize) || chunkSize <= 0) throw new Error("Kích thước khối tải video không hợp lệ.");
    let offset = uploadSession.next_offset;
    params.onProgress?.(offset, params.file.size);
    while (offset < params.file.size) {
      const end = Math.min(offset + chunkSize, params.file.size);
      const res = await apiFetch(
        `${API_BASE_URL}/v1/media/upload-sessions/${encodeURIComponent(uploadSession.session_id)}/chunks?offset=${offset}`,
        { method: "PUT", headers, body: params.file.slice(offset, end) },
      );
      if (!res.ok) throw new Error(await responseErrorMessage(res, "Tải video bị gián đoạn; có thể tiếp tục từ phần đã nhận."));
      const result = await res.json() as { next_offset: number };
      if (result.next_offset <= offset || result.next_offset > end) throw new Error("Máy chủ trả về vị trí tải video không hợp lệ.");
      offset = result.next_offset;
      params.onProgress?.(offset, params.file.size);
    }

    const completed = await apiFetch(
      `${API_BASE_URL}/v1/media/upload-sessions/${encodeURIComponent(uploadSession.session_id)}/complete`,
      { method: "POST", headers },
    );
    if (!completed.ok) throw new Error(await responseErrorMessage(completed, "Không thể hoàn tất đăng ký video."));
    try {
      storage?.removeItem(sessionKey);
    } catch {
      // A stale local entry is harmless; the server has already completed the upload.
    }
    return formatAsset(await completed.json());
  },

  // 7. Lấy phiên bản timeline mới nhất của dự án
  async getTimeline(projectId: string): Promise<TimelineVersionResponse> {
    const wsId = AuthApi.getWorkspaceId();
    const res = await apiFetch(`${API_BASE_URL}/v1/media/projects/${projectId}/timeline`, {
      headers: mediaAuthHeaders(wsId),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi tải timeline: ${res.statusText}`);
    }
    return res.json();
  },

  // 8. Lưu phiên bản timeline mới (OCC Versioning)
  async saveTimeline(projectId: string, document: TimelineDocument, expectedVersion?: number): Promise<TimelineVersionResponse> {
    const wsId = AuthApi.getWorkspaceId();
    const res = await apiFetch(`${API_BASE_URL}/v1/media/projects/${projectId}/timeline`, {
      method: "PUT",
      headers: mediaAuthHeaders(wsId, undefined, "application/json"),
      body: JSON.stringify({
        timeline: document,
        expected_version: expectedVersion,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi lưu timeline: ${res.statusText}`);
    }
    return res.json();
  },

  // 9. Kết xuất video hoàn chỉnh TikTok từ timeline
  async renderTimeline(projectId: string, timelineVersionId?: string): Promise<MediaAssetResponse> {
    const formData = new FormData();
    if (timelineVersionId) formData.append("timeline_version_id", timelineVersionId);

    const wsId = AuthApi.getWorkspaceId();
    const res = await apiFetch(`${API_BASE_URL}/v1/media/projects/${projectId}/render-timeline`, {
      method: "POST",
      headers: mediaAuthHeaders(wsId),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi kết xuất video: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },
};

