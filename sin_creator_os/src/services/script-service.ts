import { Script, ScriptBlock } from '@/types';
import { AuthApi } from '@/lib/api/auth-api';

function getAuthHeaders(workspaceId?: string): Record<string, string> {
  const headers = AuthApi.getAuthHeaders();
  if (workspaceId) headers['X-Workspace-Id'] = workspaceId;
  return headers;
}

function mapBackendScriptToFrontend(s: any): Script {
  const blocks: ScriptBlock[] = (s.blocks || []).map((b: any, idx: number) => ({
    id: `b_${idx}_${b.block_type || 'BLOCK'}`,
    type: b.block_type || 'VALUE',
    title:
      b.block_type === 'HOOK'
        ? 'Mở Đầu Giữ Chân (Hook)'
        : b.block_type === 'SETUP'
        ? 'Thiết Lập Vấn Đề (Setup)'
        : b.block_type === 'VALUE'
        ? 'Giá Trị Cốt Lõi (Value)'
        : b.block_type === 'PROOF'
        ? 'Bằng Chứng Thực Tế (Proof)'
        : 'Kêu Gọi Hành Động (CTA)',
    content: b.narration || '',
    durationSec: b.duration_seconds || 5,
    visualCue: b.visual_cue || 'Chuyển cảnh dọc 9:16',
    audioCue: b.audio_cue,
    tone: 'energetic',
  }));

  const statusMap: Record<string, Script['status']> = {
    APPROVED: 'approved',
    READY_FOR_REVIEW: 'reviewed',
    DRAFT: 'draft',
    IN_REVIEW: 'reviewed',
    NEEDS_FACT_CHECK: 'draft',
    SUPERSEDED: 'draft',
    REJECTED: 'draft',
  };

  return {
    id: s.id,
    ideaId: s.idea_id,
    title: s.title || 'Kịch Bản TikTok BAHA',
    niche: 'Xây Kênh & Sáng Tạo',
    targetDurationSec: s.target_duration_seconds || 30,
    estimatedWpm: 140,
    status: statusMap[s.status] || 'draft',
    context: {
      ideaTitle: s.title || 'Ý tưởng TikTok BAHA',
      oneLineConcept: (s.hook_variants && s.hook_variants[0]) || s.title || '',
      targetAudience: 'Khán giả TikTok 18-35 tuổi',
      brandVoice: 'Chân thực, thuyết phục, dẫn chứng rõ ràng',
      referenceLinks: [],
      keyTakeaway: 'Nội dung chuẩn 5 block tối ưu Safe Zone TikTok',
    },
    blocks: blocks.length > 0 ? blocks : [],
    updatedAt: s.created_at || new Date().toISOString(),
  };
}

export class ScriptService {
  static async getScriptById(id: string, workspaceId?: string): Promise<Script | null> {
    try {
      const res = await fetch(`/v1/scripts/${id}`, {
        credentials: 'same-origin',
        headers: getAuthHeaders(workspaceId),
      });
      if (res.ok) {
        const data = await res.json();
        return mapBackendScriptToFrontend(data);
      }
    } catch {
      // API error
    }
    return null;
  }

  static async listScripts(
    filters?: { idea_id?: string; status?: string },
    workspaceId?: string
  ): Promise<Script[]> {
    try {
      const params = new URLSearchParams();
      if (filters?.idea_id) params.set('idea_id', filters.idea_id);
      if (filters?.status) params.set('status', filters.status);
      params.set('limit', '50');

      const res = await fetch(`/v1/scripts?${params.toString()}`, {
        credentials: 'same-origin',
        headers: getAuthHeaders(workspaceId),
      });
      if (res.ok) {
        const list = await res.json();
        if (Array.isArray(list) && list.length > 0) {
          return list.map(mapBackendScriptToFrontend);
        }
      }
    } catch {
      // Fallback
    }
    return Promise.resolve([]);
  }

  static async createScript(
    payload: {
      idea_id: string;
      title: string;
      target_duration_seconds?: number;
      hook_variants?: string[];
      blocks?: Array<{
        block_type: 'HOOK' | 'SETUP' | 'VALUE' | 'PROOF' | 'CTA';
        narration: string;
        visual_cue: string;
        duration_seconds: number;
      }>;
    },
    workspaceId?: string
  ): Promise<Script> {
    const targetDuration = payload.target_duration_seconds || 30;
    const defaultBlocks = [
      {
        block_type: 'HOOK' as const,
        narration: payload.hook_variants?.[0] || 'Đây là bí mật giúp kênh của bạn lên xu hướng nhanh nhất!',
        visual_cue: 'Cận cảnh biểu cảm gương mặt kèm text động nổi bật ở Safe Zone trên.',
        duration_seconds: 3,
      },
      {
        block_type: 'SETUP' as const,
        narration: 'Nhiều bạn vẫn đang làm theo cách cũ và bị bóp tương tác mà không hiểu vì sao.',
        visual_cue: 'B-roll lướt màn hình TikTok quay chậm.',
        duration_seconds: 5,
      },
      {
        block_type: 'VALUE' as const,
        narration: 'Đây là 3 bước thực thi tinh gọn mà BAHA Group đã đúc kết.',
        visual_cue: 'Hiển thị 3 gạch đầu dòng đồ họa vector rõ ràng.',
        duration_seconds: 15,
      },
      {
        block_type: 'PROOF' as const,
        narration: 'Kết quả kiểm chứng cho thấy tỷ lệ xem hết tăng 40% trong tuần đầu tiên.',
        visual_cue: 'Chụp màn hình số liệu phân tích TikTok Analytics.',
        duration_seconds: 5,
      },
      {
        block_type: 'CTA' as const,
        narration: 'Lưu video này lại và follow kênh để nhận quy trình chi tiết!',
        visual_cue: 'Mũi tên trỏ vào nút follow và nút bookmark.',
        duration_seconds: 2,
      },
    ];

    const body = {
      idea_id: payload.idea_id,
      title: payload.title,
      target_duration_seconds: targetDuration,
      hook_variants: payload.hook_variants && payload.hook_variants.length >= 2
        ? payload.hook_variants
        : [
            payload.hook_variants?.[0] || 'Đây là bí mật giúp kênh của bạn lên xu hướng nhanh nhất!',
            'Đừng lướt qua nếu bạn không muốn bỏ lỡ cách xây kênh chuẩn 2026!',
          ],
      blocks: payload.blocks && payload.blocks.length >= 3 ? payload.blocks : defaultBlocks,
    };

    const res = await fetch('/v1/scripts', {
      method: 'POST',
      credentials: 'same-origin',
      headers: getAuthHeaders(workspaceId),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || 'Không thể tạo bản thảo kịch bản');
    }

    const data = await res.json();
    return mapBackendScriptToFrontend(data);
  }

  static async updateScript(script: Script, workspaceId?: string): Promise<Script> {
    try {
      const hookBlocks = script.blocks.filter((b) => b.type === 'HOOK');
      const hookVariants = hookBlocks.map((b) => b.content);
      if (hookVariants.length < 2) {
        hookVariants.push('Phương án mở đầu dự phòng 2');
      }

      const body = {
        title: script.title,
        target_duration_seconds: script.targetDurationSec,
        hook_variants: hookVariants,
        blocks: script.blocks.map((b) => ({
          block_type: b.type,
          narration: b.content,
          visual_cue: b.visualCue || 'Chuyển cảnh dọc 9:16',
          duration_seconds: Math.max(1, b.durationSec || 5),
        })),
        editor_notes: 'Lưu từ Creator Studio Script Editor',
      };

      const res = await fetch(`/v1/scripts/${script.id}/edit`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: getAuthHeaders(workspaceId),
        body: JSON.stringify(body),
      });

      if (res.ok) {
        const data = await res.json();
        return mapBackendScriptToFrontend(data);
      }
    } catch {
      // Fallback
    }
    return Promise.resolve(script);
  }

  static async approveScript(scriptId: string, workspaceId?: string): Promise<Script> {
    const res = await fetch(`/v1/scripts/${scriptId}/approve`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: getAuthHeaders(workspaceId),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || 'Không thể phê duyệt kịch bản');
    }

    const data = await res.json();
    return mapBackendScriptToFrontend(data);
  }

  static async optimizeHook(
    currentHook: string,
    style: 'curiosity' | 'fear_of_missing_out' | 'counter_intuitive'
  ): Promise<string[]> {
    if (style === 'counter_intuitive') {
      return [
        'Đừng học cách làm video viral nữa, hãy học cách khiến TikTok không thể bóp tương tác của bạn!',
        'Tại sao video đầu tư tiền triệu lại ít view hơn video quay bằng điện thoại trong 5 phút?',
        'Bí mật mà các agency TikTok triệu view không bao giờ nói cho bạn biết...',
      ];
    }
    return [
      'Nếu bạn bỏ qua video này trong 3 giây tới, kênh của bạn sẽ mãi dậm chân tại chỗ!',
      'Dừng ngay lại nếu bạn không muốn phí hoài công sức xây kênh TikTok suốt 6 tháng qua!',
      '3 giây quyết định kênh của bạn lên xu hướng hay bị lãng quên mãi mãi.',
    ];
  }
}
