import { AuthApi } from "@/lib/api/auth-api";

export interface PlatformLLMConfig {
  is_configured: boolean;
  is_enabled: boolean;
  base_url: string;
  model: string;
  key_fingerprint: string;
  has_api_key: boolean;
  timeout_seconds: number;
  max_output_tokens: number;
  max_input_bytes: number;
  input_usd_per_1k_tokens: number;
  output_usd_per_1k_tokens: number;
  budget_units_per_usd: number;
  updated_at: string;
}

export interface PlatformLLMConfigUpdate {
  is_enabled: boolean;
  base_url: string;
  model: string;
  new_api_key?: string | null;
  timeout_seconds: number;
  max_output_tokens: number;
  max_input_bytes: number;
  input_usd_per_1k_tokens: number;
  output_usd_per_1k_tokens: number;
  budget_units_per_usd: number;
}

export interface PlatformLLMProbeRequest {
  base_url?: string | null;
  model?: string | null;
  probe_api_key?: string | null;
}

export interface PlatformLLMProbeResult {
  ok: boolean;
  latency_ms: number;
  status_code?: number | null;
  message: string;
  models_discovered?: string[];
}

export interface PlatformLLMPublicStatus {
  is_configured: boolean;
  is_enabled: boolean;
  model: string;
  updated_at: string;
}

export class PlatformConfigService {
  /**
   * Đọc cấu hình chi tiết Cổng LLM trung tâm (Chỉ dành cho Platform Owner)
   */
  static async getConfig(): Promise<PlatformLLMConfig> {
    const headers = AuthApi.getAuthHeaders();
    const res = await fetch("/v1/platform/llm-config", {
      method: "GET",
      credentials: "same-origin",
      headers,
      cache: "no-store",
    });

    if (!res.ok) {
      if (res.status === 403) {
        throw new Error("PERMISSION_DENIED: Bạn không có quyền Platform Owner để truy cập cấu hình này.");
      }
      if (res.status === 401) {
        throw new Error("UNAUTHORIZED: Phiên đăng nhập đã hết hạn hoặc không hợp lệ.");
      }
      const errText = await res.text();
      throw new Error(`Lỗi tải cấu hình LLM (${res.status}): ${errText}`);
    }

    return await res.json();
  }

  /**
   * Cập nhật cấu hình Cổng LLM trung tâm (Chỉ dành cho Platform Owner)
   */
  static async updateConfig(payload: PlatformLLMConfigUpdate): Promise<PlatformLLMConfig> {
    const headers = AuthApi.getAuthHeaders();
    const res = await fetch("/v1/platform/llm-config", {
      method: "PUT",
      credentials: "same-origin",
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      const message = errData.detail || `Lỗi cập nhật cấu hình (${res.status})`;
      throw new Error(message);
    }

    return await res.json();
  }

  /**
   * Kiểm tra kết nối tới Cổng 9Router Gateway mà không tiêu hao token
   */
  static async probeGateway(payload: PlatformLLMProbeRequest): Promise<PlatformLLMProbeResult> {
    const headers = AuthApi.getAuthHeaders();
    const res = await fetch("/v1/platform/llm-config/probe", {
      method: "POST",
      credentials: "same-origin",
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      return {
        ok: false,
        latency_ms: 0,
        status_code: res.status,
        message: errData.detail || `Lỗi kiểm tra kết nối (${res.status})`,
        models_discovered: [],
      };
    }

    return await res.json();
  }

  /**
   * Đọc trạng thái công khai tối giản của Cổng LLM (Dành cho Non-Owner)
   */
  static async getPublicStatus(): Promise<PlatformLLMPublicStatus> {
    const res = await fetch("/v1/platform/llm-config/public-status", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error(`Lỗi tải trạng thái công khai LLM (${res.status})`);
    }

    return await res.json();
  }
}
