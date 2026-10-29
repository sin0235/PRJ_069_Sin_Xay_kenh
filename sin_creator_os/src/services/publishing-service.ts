// Service ket noi Backend Publishing & Feedback Loop API (PRJ_069)
// Tuan thu Golden Rule 9 (NO EMOJI - SVG ONLY) va Zero-Cost Local First
import { AuthApi } from "@/lib/api/auth-api";

function getAuthHeaders(workspaceId?: string): Record<string, string> {
  const headers = AuthApi.getAuthHeaders();
  if (workspaceId) {
    headers["X-Workspace-Id"] = workspaceId;
  }
  return headers;
}

export interface PublishedLinkItem {
  id: string;
  workspace_id: string;
  script_draft_version_id: string;
  platform: string;
  external_post_id: string;
  external_post_url: string;
  channel_id?: string | null;
  is_paid: boolean;
  status: string;
  published_at?: string | null;
  created_at: string;
  detached_at?: string | null;
}

export interface CreatePublishedLinkPayload {
  script_draft_version_id: string;
  platform?: string;
  external_post_id: string;
  external_post_url: string;
  channel_id?: string;
  is_paid?: boolean;
  published_at?: string;
}

export interface LearningSignalItem {
  id: string;
  workspace_id: string;
  published_content_link_id: string;
  signal_type: string;
  confidence_score: number;
  recommendation_action: string;
  formula_explanation: string;
  limitations: string;
  created_at: string;
}

export class PublishingService {
  /**
   * Tao lien ket bai dang TikTok moi vao backend
   */
  static async createPublishedLink(
    payload: CreatePublishedLinkPayload,
    workspaceId?: string
  ): Promise<{ success: boolean; data?: PublishedLinkItem; error?: string }> {
    try {
      const res = await fetch("/v1/feedback/published-links", {
        method: "POST",
        credentials: "same-origin",
        headers: getAuthHeaders(workspaceId),
        body: JSON.stringify({
          script_draft_version_id: payload.script_draft_version_id,
          platform: payload.platform || "tiktok",
          external_post_id: payload.external_post_id,
          external_post_url: payload.external_post_url,
          channel_id: payload.channel_id || null,
          is_paid: payload.is_paid || false,
          published_at: payload.published_at || new Date().toISOString(),
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return {
          success: false,
          error: err.detail?.message || err.detail || `Loi xuat ban: Ma loi ${res.status}`,
        };
      }

      const data: PublishedLinkItem = await res.json();
      return { success: true, data };
    } catch (e: any) {
      return {
        success: false,
        error: e?.message || "Khong the ket noi den may chu API xuat ban.",
      };
    }
  }

  /**
   * Lay danh sach cac bai dang da phat hanh / len lich
   */
  static async listPublishedLinks(
    opts: { scriptId?: string; status?: string; workspaceId?: string } = {}
  ): Promise<PublishedLinkItem[]> {
    const { scriptId, status, workspaceId } = opts;
    try {
      const params = new URLSearchParams();
      if (scriptId) params.append("script_id", scriptId);
      if (status) params.append("status", status);

      const query = params.toString() ? `?${params.toString()}` : "";
      const res = await fetch(`/v1/feedback/published-links${query}`, {
        credentials: "same-origin",
        headers: getAuthHeaders(workspaceId),
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.items)) {
          return data.items;
        }
      }
    } catch {
      // Fallback
    }
    return [];
  }

  /**
   * Thao go lien ket bai dang (detach)
   */
  static async detachPublishedLink(
    linkId: string,
    reason: string = "USER_REQUESTED_DETACH",
    workspaceId?: string
  ): Promise<boolean> {
    try {
      const res = await fetch(
        `/v1/feedback/published-links/${encodeURIComponent(linkId)}/detach?reason=${encodeURIComponent(reason)}`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: getAuthHeaders(workspaceId),
        }
      );
      return res.ok;
    } catch {
      return false;
    }
  }

  /**
   * Lay danh sach tin hieu hoc may (learning signals) cho trang Analytics
   */
  static async listLearningSignals(
    linkId?: string,
    workspaceId?: string
  ): Promise<LearningSignalItem[]> {
    try {
      const param = linkId ? `?link_id=${encodeURIComponent(linkId)}` : "";
      const res = await fetch(`/v1/feedback/learning-signals${param}`, {
        credentials: "same-origin",
        headers: getAuthHeaders(workspaceId),
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.items)) {
          return data.items;
        }
      }
    } catch {
      // Fallback
    }
    return [];
  }
}
