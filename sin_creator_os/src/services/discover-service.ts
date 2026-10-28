import { ContentItem, ContentBadge } from "@/types/content";
import { AuthApi } from "@/lib/api/auth-api";

const API_BASE_URL = "";

export interface DiscoverFilters {
  query?: string;
  niche?: string;
  period?: "today" | "7d" | "30d" | "all";
  minViews?: number;
  engagementRate?: number;
  badge?: string;
  sortBy?: "trending" | "views" | "engagement" | "velocity";
}

export interface EvidenceExcerptItem {
  id: string;
  source_record_id: string;
  excerpt_type: string;
  text_content: string;
  author_handle?: string;
  observed_at?: string;
  confidence_score?: number;
  is_verified?: boolean;
}

export class DiscoverService {
  /**
   * Tìm kiếm video & tư liệu nguồn thực tế từ Backend CSDL (Ground Truth)
   */
  static async searchContent(
    filters?: DiscoverFilters,
    workspaceId: string = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
  ): Promise<ContentItem[]> {
    try {
      const headers = AuthApi.getAuthHeaders();
      if (workspaceId) headers["X-Workspace-Id"] = workspaceId;

      const res = await fetch(`${API_BASE_URL}/v1/sources/records?limit=50`, {
        headers,
        cache: "no-store",
      });

      if (res.ok) {
        const records = await res.json();
        if (Array.isArray(records) && records.length > 0) {
          const mapped: ContentItem[] = records.map((r: any): ContentItem => {
            const views = r.view_count ?? null;
            const likes = r.like_count ?? null;
            const comments = r.comment_count ?? null;
            const shares = r.share_count ?? null;
            const hasMetrics = [views, likes, comments, shares, r.engagement_rate].some(
              (value) => value !== null && value !== undefined
            );
            const engagementRate = r.engagement_rate ?? (views !== null && likes !== null && views > 0
              ? Number(((likes / views) * 100).toFixed(1))
              : null);
            const badges: ContentBadge[] = [];
            if (r.is_trending) badges.push("trending");
            if (engagementRate !== null && engagementRate >= 6) badges.push("high_engagement");
            const channelId = r.channel_id || "";

            return {
              id: r.id,
              title: r.title || "",
              caption: r.caption || "",
              thumbnailUrl: r.thumbnail_url || "",
              videoUrl: r.canonical_url || undefined,
              channelId,
              channelName: r.channel_name || "",
              channelAvatar: r.channel_avatar_url || "",
              status: "published",
              publishDate: r.published_at || undefined,
              durationSec: r.duration_seconds ?? 0,
              contentPillar: r.content_pillar || r.topic || "",
              hook: r.hook || (r.caption || "").slice(0, 80),
              isAiGenerated: Boolean(r.synthetic),
              badges,
              metrics: hasMetrics ? {
                views,
                likes,
                comments,
                shares,
                engagementRate,
                watchTimeSec: r.avg_watch_time_seconds ?? null,
                completionRate: r.completion_rate ?? null,
              } : undefined,
              evidence: [],
              detectedTopic: r.topic || "",
              audienceSignal: r.audience_signal || "",
              growthVelocity: r.growth_velocity || "",
              soundName: r.sound_name || undefined,
            };
          });

          let filtered = mapped;
          if (filters?.query) {
            const q = filters.query.toLowerCase();
            filtered = filtered.filter(
              (v) =>
                v.title.toLowerCase().includes(q) ||
                v.caption.toLowerCase().includes(q) ||
                v.channelName.toLowerCase().includes(q)
            );
          }
          if (filters?.niche && filters.niche !== "all") {
            filtered = filtered.filter((v) =>
              v.contentPillar.toLowerCase().includes(filters.niche!.toLowerCase())
            );
          }

          if (filtered.length > 0) {
            return filtered;
          }
        }
      }
    } catch {
      // API error handling
    }

    return [];
  }

  /**
   * Nạp trích dẫn bằng chứng thực tế từ backend
   */
  static async getEvidenceExcerpt(
    evidenceId: string,
    workspaceId: string = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
  ): Promise<EvidenceExcerptItem | null> {
    try {
      const headers = AuthApi.getAuthHeaders();
      if (workspaceId) headers["X-Workspace-Id"] = workspaceId;

      const res = await fetch(`${API_BASE_URL}/v1/sources/evidence/${evidenceId}`, {
        headers,
      });

      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback null
    }

    return null;
  }

  /**
   * Phân tích nội dung video chi tiết
   */

}
