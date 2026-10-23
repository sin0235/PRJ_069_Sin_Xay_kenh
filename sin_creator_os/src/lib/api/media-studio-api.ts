// Client Service giao tiếp với Backend Media Studio API (PRJ_069)
// Tích hợp Flow Music Plus, Google Flow 9:16 và FFmpeg Auto-Ducking
import { AuthApi } from "@/lib/api/auth-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function formatAsset(asset: MediaAssetResponse): MediaAssetResponse {
  if (asset && asset.url && asset.url.startsWith("/")) {
    asset.url = `${API_BASE_URL}${asset.url}`;
  }
  return asset;
}

async function fetchAssetBlob(url: string): Promise<Blob> {
  const res = await fetch(url, {
    headers: {
      "X-Workspace-Id": AuthApi.getWorkspaceId(),
      Authorization: `Bearer ${AuthApi.getAuthToken()}`,
    },
  });
  if (!res.ok) throw new Error(`Không thể tải tệp media (${res.status}).`);
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
  approval_state: string;
  url?: string;
  created_at: string;
}

export interface ProductionProjectResponse {
  id: string;
  workspace_id: string;
  title: string;
  status: string;
  created_at: string;
}

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
}

export interface TimelineDocument {
  width?: number;
  height?: number;
  fps?: number;
  clips: TimelineClip[];
  voice_track?: TimelineAudioTrack | null;
  music_track?: TimelineAudioTrack | null;
  captions?: TimelineCaption[];
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
  async listProjects(): Promise<ProductionProjectResponse[]> {
    const res = await fetch(`${API_BASE_URL}/v1/media/projects`, {
      headers: {
        "X-Workspace-Id": AuthApi.getWorkspaceId(),
        Authorization: `Bearer ${AuthApi.getAuthToken()}`,
      },
    });
    if (!res.ok) throw new Error(`Không thể tải dự án (${res.status}).`);
    return res.json();
  },

  async createProject(title: string): Promise<ProductionProjectResponse> {
    const res = await fetch(`${API_BASE_URL}/v1/media/projects`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
      body: JSON.stringify({ title }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Không thể tạo dự án (${res.status}).`);
    }
    return res.json();
  },

  async openGoogleFlowLogin(): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/v1/media/flow/login`, {
      method: "POST",
      headers: {
        "X-Workspace-Id": AuthApi.getWorkspaceId(),
        Authorization: `Bearer ${AuthApi.getAuthToken()}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message_safe || err.detail?.message || err.detail || `Không thể mở đăng nhập Google Flow (${res.status}).`);
    }
  },

  async getMusicCapabilities(): Promise<MusicCapabilitiesResponse> {
    const res = await fetch(`${API_BASE_URL}/v1/media/music/capabilities`, {
      method: "GET",
      headers: {
        "X-Workspace-Id": AuthApi.getWorkspaceId(),
        Authorization: `Bearer ${AuthApi.getAuthToken()}`,
      },
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

    const res = await fetch(`${API_BASE_URL}/v1/media/assets/${assetId}/review`, {
      method: "POST",
      headers: {
        "X-Workspace-Id": AuthApi.getWorkspaceId(),
        Authorization: `Bearer ${AuthApi.getAuthToken()}`,
      },
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
    if (params.idempotency_key) formData.append("idempotency_key", params.idempotency_key);
    formData.append("normalize_tiktok", String(params.normalize_tiktok !== false));

    const authToken = params.token || AuthApi.getAuthToken();
    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/music/generate`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message_safe || err.detail?.message || err.detail || `Lỗi tạo nhạc: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  async waitForMusicResult(idempotencyKey: string, signal: AbortSignal): Promise<MediaAssetResponse> {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 10 * 60 * 1000) {
      try {
        const res = await fetch(`${API_BASE_URL}/v1/media/music/jobs/${encodeURIComponent(idempotencyKey)}`, {
          headers: {
            "X-Workspace-Id": AuthApi.getWorkspaceId(),
            Authorization: `Bearer ${AuthApi.getAuthToken()}`,
          },
          signal,
        });
        if (res.status === 404) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          continue;
        }
        if (!res.ok) throw new Error(`Không thể kiểm tra trạng thái tạo nhạc (${res.status}).`);

        const job: MusicJobStatusResponse = await res.json();
        if (job.state === "SUCCEEDED") {
          if (!job.asset) throw new Error("Tác vụ đã hoàn tất nhưng không tìm thấy tệp nhạc đã lưu.");
          return formatAsset(job.asset);
        }
        if (job.state === "FAILED" || job.state === "NEEDS_RECONCILIATION") {
          throw new Error(job.error_message || job.error_code || "Tác vụ tạo nhạc không hoàn tất.");
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

    const authToken = params.token || AuthApi.getAuthToken();
    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/audio/mix`, {
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

    const authToken = AuthApi.getAuthToken();
    const wsId = AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/video/prompt/compile`, {
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
    formData.append("remove_watermark", String(params.remove_watermark !== false));
    if (params.project_id) formData.append("project_id", params.project_id);

    const authToken = params.token || AuthApi.getAuthToken();
    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/video/generate`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message_safe || err.detail?.message || err.detail || `Lỗi tạo video: ${res.statusText}`);
    }
    const data: MediaAssetResponse = await res.json();
    return formatAsset(data);
  },

  // 3b. Mo rong video 16:9 (Omni 10s hoac tai len) sang 9:16 chuan TikTok
  async expandVideo(params: { file?: File; asset_id?: string; project_id?: string; blur_strength?: number; remove_watermark?: boolean }): Promise<MediaAssetResponse> {
    const formData = new FormData();
    if (params.file) formData.append("file", params.file);
    if (params.asset_id) formData.append("asset_id", params.asset_id);
    if (params.project_id) formData.append("project_id", params.project_id);
    formData.append("blur_strength", String(params.blur_strength ?? 25));
    formData.append("remove_watermark", String(params.remove_watermark !== false));

    const authToken = AuthApi.getAuthToken();
    const wsId = AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/video/expand`, {
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

    const authToken = AuthApi.getAuthToken();
    const wsId = AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/video/remove-watermark`, {
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

    const authToken = params.token || AuthApi.getAuthToken();
    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/video/assemble`, {
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

  async listAssets(opts: string | { workspace_id?: string; project_id?: string; token?: string } = "default_ws", token?: string): Promise<MediaAssetResponse[]> {
    const wsId = typeof opts === "string" ? opts : (opts.workspace_id || AuthApi.getWorkspaceId());
    const tok = typeof opts === "string" ? token : opts.token;
    const authToken = tok || AuthApi.getAuthToken();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      "Authorization": `Bearer ${authToken}`,
    };
    const projectId = typeof opts === "string" ? undefined : opts.project_id;
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";

    const res = await fetch(`${API_BASE_URL}/v1/media/assets${query}`, {
      headers,
    });

    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data.map(formatAsset) : [];
  },

  // 6. Tải lên tệp tư liệu (ảnh, video, audio)
  async uploadAsset(params: UploadAssetParams): Promise<MediaAssetResponse> {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.project_id) formData.append("project_id", params.project_id);
    formData.append("expected_category", params.expected_category || "video");
    formData.append("source_product", params.source_product || "UPLOAD");

    const authToken = params.token || AuthApi.getAuthToken();
    const wsId = params.workspace_id || AuthApi.getWorkspaceId();
    const headers: Record<string, string> = {
      "X-Workspace-Id": wsId,
      Authorization: `Bearer ${authToken}`,
    };

    const res = await fetch(`${API_BASE_URL}/v1/media/upload`, {
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

  // 7. Lấy phiên bản timeline mới nhất của dự án
  async getTimeline(projectId: string): Promise<TimelineVersionResponse> {
    const authToken = AuthApi.getAuthToken();
    const wsId = AuthApi.getWorkspaceId();
    const res = await fetch(`${API_BASE_URL}/v1/media/projects/${projectId}/timeline`, {
      headers: {
        "X-Workspace-Id": wsId,
        Authorization: `Bearer ${authToken}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || `Lỗi tải timeline: ${res.statusText}`);
    }
    return res.json();
  },

  // 8. Lưu phiên bản timeline mới (OCC Versioning)
  async saveTimeline(projectId: string, document: TimelineDocument, expectedVersion?: number): Promise<TimelineVersionResponse> {
    const authToken = AuthApi.getAuthToken();
    const wsId = AuthApi.getWorkspaceId();
    const res = await fetch(`${API_BASE_URL}/v1/media/projects/${projectId}/timeline`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Workspace-Id": wsId,
        Authorization: `Bearer ${authToken}`,
      },
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

    const authToken = AuthApi.getAuthToken();
    const wsId = AuthApi.getWorkspaceId();
    const res = await fetch(`${API_BASE_URL}/v1/media/projects/${projectId}/render-timeline`, {
      method: "POST",
      headers: {
        "X-Workspace-Id": wsId,
        Authorization: `Bearer ${authToken}`,
      },
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

