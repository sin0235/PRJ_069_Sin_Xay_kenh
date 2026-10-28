import { Script, ScriptBlock } from '@/types';
import { AuthApi } from '@/lib/api/auth-api';

const API_BASE_URL = '';

function getAuthHeaders(workspaceId: string = 'b6102190-1f6f-5624-bfb8-2e1091fa2560'): Record<string, string> {
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
    durationSec: b.duration_seconds ?? 0,
    visualCue: b.visual_cue || '',
    audioCue: b.audio_cue,
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
    title: s.title || '',
    niche: '',
    targetDurationSec: s.target_duration_seconds ?? 0,
    estimatedWpm: s.estimated_wpm ?? 0,
    status: statusMap[s.status] || 'draft',
    context: {
      ideaTitle: s.title || '',
      oneLineConcept: s.hook_variants?.[0] || '',
      targetAudience: '',
      brandVoice: '',
      referenceLinks: s.reference_links || [],
      keyTakeaway: '',
    },
    blocks,
    updatedAt: s.updated_at || s.created_at || "",
  };
}

export class ScriptService {
  static async getScriptById(id: string, workspaceId: string = 'b6102190-1f6f-5624-bfb8-2e1091fa2560'): Promise<Script> {
    const res = await fetch(`${API_BASE_URL}/v1/scripts/${id}`, {
      headers: getAuthHeaders(workspaceId),
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(res.status === 404 ? 'Không tìm thấy kịch bản.' : 'Không tải được kịch bản.');
    return mapBackendScriptToFrontend(await res.json());
  }

  static async listScripts(
    filters?: { idea_id?: string; status?: string },
    workspaceId: string = 'b6102190-1f6f-5624-bfb8-2e1091fa2560'
  ): Promise<Script[]> {
    const params = new URLSearchParams();
    if (filters?.idea_id) params.set('idea_id', filters.idea_id);
    if (filters?.status) params.set('status', filters.status);
    params.set('limit', '50');

    const res = await fetch(`${API_BASE_URL}/v1/scripts?${params.toString()}`, {
      headers: getAuthHeaders(workspaceId),
      cache: 'no-store',
    });
    if (!res.ok) throw new Error('Không tải được danh sách kịch bản.');
    const list = await res.json();
    return Array.isArray(list) ? list.map(mapBackendScriptToFrontend) : [];
  }

  static async createScript(
    payload: {
      idea_id: string;
      title: string;
      target_duration_seconds?: number;
      hook_variants: string[];
      blocks: Array<{
        block_type: 'HOOK' | 'SETUP' | 'VALUE' | 'PROOF' | 'CTA';
        narration: string;
        visual_cue: string;
        duration_seconds: number;
      }>;
    },
    workspaceId: string = 'b6102190-1f6f-5624-bfb8-2e1091fa2560'
  ): Promise<Script> {
    if (payload.hook_variants.length < 2 || payload.blocks.length < 3) {
      throw new Error('Kịch bản cần ít nhất 2 biến thể mở đầu và 3 phân đoạn.');
    }
    const res = await fetch(`${API_BASE_URL}/v1/scripts`, {
      method: 'POST',
      headers: getAuthHeaders(workspaceId),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || 'Không thể tạo bản thảo kịch bản.');
    }
    return mapBackendScriptToFrontend(await res.json());
  }

  static async updateScript(script: Script, workspaceId: string = 'b6102190-1f6f-5624-bfb8-2e1091fa2560'): Promise<Script> {
    const hookVariants = script.blocks.filter((b) => b.type === 'HOOK').map((b) => b.content);
    if (hookVariants.length < 2) {
      throw new Error('Kịch bản cần ít nhất 2 biến thể mở đầu trước khi lưu.');
    }

    const body = {
      title: script.title,
      target_duration_seconds: script.targetDurationSec,
      hook_variants: hookVariants,
      blocks: script.blocks.map((b) => ({
        block_type: b.type,
        narration: b.content,
        visual_cue: b.visualCue || '',
        duration_seconds: Math.max(1, b.durationSec || 1),
      })),
      editor_notes: 'Lưu từ Creator Studio Script Editor',
    };
    const res = await fetch(`${API_BASE_URL}/v1/scripts/${script.id}/edit`, {
      method: 'POST',
      headers: getAuthHeaders(workspaceId),
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || 'Không thể lưu kịch bản.');
    }
    return mapBackendScriptToFrontend(await res.json());
  }

  static async approveScript(scriptId: string, workspaceId: string = 'b6102190-1f6f-5624-bfb8-2e1091fa2560'): Promise<Script> {
    const res = await fetch(`${API_BASE_URL}/v1/scripts/${scriptId}/approve`, {
      method: 'POST',
      headers: getAuthHeaders(workspaceId),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || 'Không thể phê duyệt kịch bản');
    }

    const data = await res.json();
    return mapBackendScriptToFrontend(data);
  }

}
