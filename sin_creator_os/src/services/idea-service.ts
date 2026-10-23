import { ContentIdea, IdeaGenerationConfig, IdeaReviewPayload, IdeaStatus } from '@/types';
import { AuthApi } from '@/lib/api/auth-api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_WORKSPACE_ID = 'default_ws';

export class IdeaService {
  /**
   * Lấy danh sách thẻ ý tưởng từ backend API trực tiếp (Ground Truth)
   */
  static async getIdeas(status?: string, workspaceId?: string): Promise<ContentIdea[]> {
    try {
      const headers = AuthApi.getAuthHeaders();
      const activeWs = workspaceId || headers['X-Workspace-Id'] || DEFAULT_WORKSPACE_ID;
      headers['X-Workspace-Id'] = activeWs;

      const queryParam = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';
      const res = await fetch(`${API_BASE_URL}/v1/ideation/cards${queryParam}`, {
        headers,
        cache: 'no-store',
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data.map((card: any) => ({
            id: card.id,
            version: card.version || 1,
            title: card.title,
            oneLineConcept: card.target_need || card.title,
            hook: card.hook,
            targetViewer: card.target_audience || 'Khán giả mục tiêu',
            painOrDesire: card.target_need || '',
            contentAngle: card.content_angle,
            videoStructure: {
              hook: card.hook,
              setup: 'Vấn đề & Bối cảnh thực tế',
              value: card.content_angle,
              proof: 'Bằng chứng thực nghiệm thị trường',
              cta: 'Theo dõi để cập nhật thêm!',
            },
            cta: 'Đăng ký kênh để không bỏ lỡ nội dung mới!',
            topic: card.target_need || 'Nội dung cốt lõi',
            contentPillar: card.topic || 'Chiến lược nội dung',
            audience: card.target_audience || 'Khán giả mục tiêu',
            format: 'Talking Head',
            expectedObjective: 'High Engagement',
            status: (card.status as IdeaStatus) || 'READY_FOR_REVIEW',
            createdBy: card.creator_id || card.created_by || 'AI Generator',
            scores: {
              relevance: Math.round((card.overall_score || 8.0) * 10),
              trend: Math.round((card.trend_score || 8.5) * 10),
              audienceFit: Math.round((card.audience_fit_score || 8.8) * 10),
              novelty: Math.round((card.novelty_score || 8.5) * 10),
              productionDifficulty: 'medium',
              overall: Math.round((card.overall_score || 8.0) * 10),
            },
            freshness: 'Rising',
            estimatedProductionEffort: '15 phút',
            whyThisIdea: card.evidence_notes || 'Được hỗ trợ bởi dữ liệu trích dẫn thị trường.',
            evidence: [],
            relatedSuccessfulContent: [],
            reviewerNotes: card.review_reason || card.reviewer_notes,
            createdAt: card.created_at || new Date().toISOString(),
          }));
        }
      }
    } catch {
      // API error
    }

    return [];
  }

  /**
   * Thực hiện đánh giá / kiểm duyệt thẻ ý tưởng
   * Tuân thủ khóa lạc quan OCC và Rào chắn Bốn Mắt (Four-Eyes Principle)
   */
  static async reviewIdea(
    id: string,
    action: 'APPROVE' | 'REJECT' | 'REQUEST_EVIDENCE' | 'REOPEN',
    expectedStatus: string,
    expectedVersion: number,
    reviewerNotes: string = 'Đã kiểm tra bằng chứng và tính an toàn',
    workspaceId?: string
  ): Promise<{ success: boolean; error?: string; updatedCard?: any }> {
    try {
      const headers = AuthApi.getAuthHeaders();
      const activeWs = workspaceId || headers['X-Workspace-Id'] || DEFAULT_WORKSPACE_ID;
      headers['X-Workspace-Id'] = activeWs;

      const payload: IdeaReviewPayload = {
        action,
        expected_status: expectedStatus,
        expected_version: expectedVersion,
        review_reason: reviewerNotes,
      };

      const res = await fetch(`${API_BASE_URL}/v1/ideation/cards/${id}/review`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (res.status === 409) {
        return {
          success: false,
          error: 'Xung đột phiên bản (HTTP 409 Stale Version): Thẻ ý tưởng này đã được sửa đổi bởi người khác. Vui lòng tải lại trang để xem phiên bản mới nhất.',
        };
      }

      if (res.status === 403) {
        const errJson = await res.json().catch(() => ({}));
        return {
          success: false,
          error: errJson.detail || 'Quy tắc Bốn Mắt: Người tạo ý tưởng không được phép tự phê duyệt (APPROVE) tác phẩm của chính mình.',
        };
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return {
          success: false,
          error: err.detail || `Không thể hoàn tất thao tác đánh giá (Mã lỗi: ${res.status}).`,
        };
      }

      const updated = await res.json();
      return { success: true, updatedCard: updated };
    } catch (e: any) {
      return { success: false, error: e?.message || 'Lỗi mạng khi kết nối máy chủ.' };
    }
  }

  /**
   * Cập nhật trạng thái thẻ ý tưởng đơn giản
   */
  static async updateIdeaStatus(id: string, status: IdeaStatus): Promise<ContentIdea | null> {
    const ideas = await this.getIdeas();
    const item = ideas.find((i) => i.id === id);
    if (item) {
      item.status = status;
      return item;
    }
    return null;
  }

  /**
   * Lấy chi tiết thẻ ý tưởng
   */
  static async getIdeaById(id: string): Promise<ContentIdea | null> {
    const ideas = await this.getIdeas();
    return ideas.find((i) => i.id === id) || null;
  }

  /**
   * Sinh thẻ ý tưởng mới từ Backend AI Engine (Hỗ trợ cả 9Router LLM và Offline Template)
   */
  static async generateIdeas(
    config: IdeaGenerationConfig & { briefVersionId?: string; allowHypotheses?: boolean },
    workspaceId: string = 'default_ws'
  ): Promise<{ success: boolean; ideas: ContentIdea[]; error?: string; generationSource?: string }> {
    try {
      const headers = AuthApi.getAuthHeaders();
      const activeWs = workspaceId || headers['X-Workspace-Id'] || DEFAULT_WORKSPACE_ID;
      headers['X-Workspace-Id'] = activeWs;

      // Sinh Idempotency-Key chống trùng lặp
      const idempKey = `idemp_ui_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
      headers['Idempotency-Key'] = idempKey;

      const briefId = config.briefVersionId || config.niche || 'bbv_baha_v1';
      const numIdeas = typeof config.desiredQuantity === 'number' ? config.desiredQuantity : parseInt(config.desiredQuantity as any, 10) || 3;

      const res = await fetch(`${API_BASE_URL}/v1/ideation/generate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          brief_version_id: briefId,
          num_ideas: Math.max(1, Math.min(20, numIdeas)),
          allow_hypotheses: config.allowHypotheses !== undefined ? config.allowHypotheses : true,
          max_cost_usd: 1.0,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        const errorMsg = errJson.message_safe || errJson.detail || `Lỗi máy chủ (${res.status})`;
        return { success: false, ideas: [], error: errorMsg };
      }

      const data = await res.json();
      const rawIdeas = data.ideas || data.cards || [];

      if (Array.isArray(rawIdeas) && rawIdeas.length > 0) {
        const mappedIdeas: ContentIdea[] = rawIdeas.map((c: any) => ({
          id: c.id,
          version: c.version || 1,
          title: c.title,
          oneLineConcept: c.target_need || c.title,
          hook: c.hook,
          targetViewer: c.target_audience || 'Khán giả mục tiêu',
          painOrDesire: c.target_need || '',
          contentAngle: c.content_angle,
          videoStructure: {
            hook: c.hook,
            setup: 'Vấn đề & Bối cảnh',
            value: c.content_angle,
            proof: 'Bằng chứng thực nghiệm',
            cta: 'Theo dõi để cập nhật thêm!',
          },
          cta: 'Đăng ký kênh để không bỏ lỡ!',
          topic: c.target_need || 'Nội dung cốt lõi',
          contentPillar: c.topic || 'Chiến lược nội dung',
          audience: c.target_audience || 'Khán giả mục tiêu',
          format: 'Talking Head',
          expectedObjective: 'High Engagement',
          status: 'READY_FOR_REVIEW',
          createdBy: data.generation_source === 'llm_router' ? '9Router AI' : 'Offline Template Engine',
          scores: {
            relevance: Math.round((c.overall_score || 8.0) * 10),
            trend: Math.round((c.trend_score || 8.5) * 10),
            audienceFit: Math.round((c.audience_fit_score || 8.8) * 10),
            novelty: Math.round((c.novelty_score || 8.5) * 10),
            productionDifficulty: 'medium',
            overall: Math.round((c.overall_score || 8.0) * 10),
          },
          freshness: 'Rising',
          estimatedProductionEffort: '15 phút',
          whyThisIdea: c.evidence_notes || 'Sinh ra từ bằng chứng thực tế thị trường.',
          evidence: [],
          relatedSuccessfulContent: [],
          createdAt: new Date().toISOString(),
        }));

        return {
          success: true,
          ideas: mappedIdeas,
          generationSource: data.generation_source || 'llm_router'
        };
      }

      return {
        success: true,
        ideas: [],
        error: data.message || 'Không có ý tưởng nào được sinh ra.',
        generationSource: data.generation_source
      };
    } catch (e: any) {
      return { success: false, ideas: [], error: e?.message || 'Lỗi mạng khi gọi API sinh ý tưởng.' };
    }
  }
}

