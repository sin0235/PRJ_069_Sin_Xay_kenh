// Client Service giao tiếp với Content Intelligence API (PRJ_069)
// Tích hợp dữ liệu CSDL thực: Ý tưởng, Kịch bản, Tư liệu nguồn và Chỉ số

import { AuthApi } from './auth-api';

export interface IdeaCardDTO {
  id: string;
  workspace_id: string;
  brief_version_id: string;
  title: string;
  target_need: string;
  hook: string;
  content_angle: string;
  confidence_tier: string;
  status: string;
  overall_score: number;
  evidence_excerpt_ids: string[];
  version: number;
  created_at: string;
  citations?: Array<{ source_id: string; quote: string }>;
}

export interface ScriptBlockDTO {
  block_type: 'HOOK' | 'SETUP' | 'VALUE' | 'PROOF' | 'CTA';
  narration: string;
  visual_cue: string;
  duration_seconds: number;
  start_seconds?: number;
  end_seconds?: number;
}

export interface ClaimCheckDTO {
  claim_text: string;
  claim_type: string;
  verification_status: 'VERIFIED' | 'NEEDS_FACT_CHECK' | 'BLOCKING';
  notes?: string;
}

export interface ScriptDraftDTO {
  id: string;
  workspace_id: string;
  idea_id: string;
  version: number;
  title: string;
  target_duration_seconds: number;
  actual_duration_seconds?: number;
  hook_variants?: string[];
  blocks: ScriptBlockDTO[];
  claims: ClaimCheckDTO[];
  status: string;
  approved_by_user_id?: string;
  approved_at?: string;
  created_at: string;
}

export interface SourceRecordDTO {
  id: string;
  workspace_id: string;
  provider_id: string;
  raw_external_id: string;
  canonical_url: string;
  title: string;
  caption: string;
  rights_basis: string;
  observed_at: string;
  is_purged: boolean;
  created_at: string;
}

export class ContentApi {
  static async getIdeaCards(status?: string): Promise<IdeaCardDTO[]> {
    try {
      const q = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';
      const res = await fetch(`/v1/ideation/cards${q}`, {
        headers: AuthApi.getAuthHeaders(),
      });
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    } catch {
      return [];
    }
  }

  static async getScripts(status?: string): Promise<ScriptDraftDTO[]> {
    try {
      const q = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';
      const res = await fetch(`/v1/scripts${q}`, {
        headers: AuthApi.getAuthHeaders(),
      });
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    } catch {
      return [];
    }
  }

  static async getScriptById(scriptId: string): Promise<ScriptDraftDTO | null> {
    try {
      const res = await fetch(`/v1/scripts/${scriptId}`, {
        headers: AuthApi.getAuthHeaders(),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  static async approveScript(scriptId: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const res = await fetch(`/v1/scripts/${scriptId}/approve`, {
        method: 'POST',
        headers: AuthApi.getAuthHeaders(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return { success: false, error: err.detail || 'Không thể phê duyệt kịch bản.' };
      }
      return { success: true, data: await res.json() };
    } catch (e: any) {
      return { success: false, error: e?.message || 'Lỗi mạng khi kết nối máy chủ.' };
    }
  }

  static async getSourceRecords(): Promise<SourceRecordDTO[]> {
    try {
      const res = await fetch("/v1/sources/records", {
        headers: AuthApi.getAuthHeaders(),
      });
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    } catch {
      return [];
    }
  }
}
