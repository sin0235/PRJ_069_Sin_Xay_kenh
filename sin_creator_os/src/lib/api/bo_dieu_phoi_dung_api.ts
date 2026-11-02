/**
 * Client API Bo Dieu Phoi Dung Video Chuyen Nghiep (Director Harness)
 * Tuan thu BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2 & AGENTS.md (100% SVG, NO EMOJI)
 */

import { AuthApi } from "@/lib/api/auth-api";

export interface DinhDanhPhien {
  run_id: string;
  project_id: string;
  workspace_id: string;
  actor_id: string;
  base_revision: number;
  base_hash: string;
  policy_version: string;
}

export interface CheckpointPhien {
  checkpoint_id: string;
  run_id: string;
  project_id: string;
  step_count: number;
  consecutive_error_count: number;
  last_error_fingerprint: string | null;
  status: string;
  saved_draft_ids: string[];
  pending_operation_ids: string[];
  cost_reserved_usd: number;
  cost_actual_usd: number;
  updated_at_epoch: number;
}

export interface BanNhapDung {
  draft_id: string;
  run_id: string;
  project_id: string;
  workspace_id: string;
  base_revision: number;
  base_hash: string;
  draft_revision: number;
  draft_hash: string;
  timeline: Record<string, unknown>;
  is_locked: boolean;
  is_committed: boolean;
  committed_version?: number | null;
}

export interface KetQuaCongCu {
  operation_id: string;
  status: string;
  revision_after: number;
  hash_after: string;
  changed_ids: string[];
  cost_units: number;
  error_code?: string | null;
  message: string;
}

export interface GoiBanGiao {
  bundle_id: string;
  project_id: string;
  revision: number;
  timeline_hash: string;
  export_format: string;
  files: string[];
  loss_report: Record<string, string[]>;
}

const API_BASE = "";

export const boDieuPhoiDungApi = {
  async taoPhien(projectId: string, baseRevision: number, baseHash: string): Promise<DinhDanhPhien> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/phien`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
      body: JSON.stringify({ base_revision: baseRevision, base_hash: baseHash }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Loi tao phien (${res.status})`);
    }
    return res.json();
  },

  async layTrangThaiPhien(projectId: string, runId: string): Promise<CheckpointPhien> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/phien/${runId}`, {
      headers: AuthApi.getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Khong tim thay phien ${runId}`);
    }
    return res.json();
  },

  async tiepTucPhien(projectId: string, runId: string): Promise<CheckpointPhien> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/phien/${runId}/tiep-tuc`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Khong the tiep tuc phien ${runId}`);
    }
    return res.json();
  },

  async huyPhien(projectId: string, runId: string): Promise<void> {
    await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/phien/${runId}/huy`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
    });
  },

  async taoBanNhap(projectId: string, runId: string, timelineBase: Record<string, unknown>): Promise<BanNhapDung> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/ban-nhap`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
      body: JSON.stringify({ run_id: runId, timeline_base: timelineBase }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Loi tao ban nhap (${res.status})`);
    }
    return res.json();
  },

  async thucHienLenh(
    projectId: string,
    draftId: string,
    expectedRevision: number,
    commands: Array<{ operation_id: string; draft_id: string; expected_draft_revision: number; type: string; payload: Record<string, unknown> }>
  ): Promise<KetQuaCongCu> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/ban-nhap/${draftId}/lenh`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
      body: JSON.stringify({ expected_draft_revision: expectedRevision, commands }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Loi thuc hien lenh (${res.status})`);
    }
    return res.json();
  },

  async commitBanNhap(projectId: string, draftId: string, expectedRevision: number, approvalId: string): Promise<{ status: string; committed_version: number }> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/ban-nhap/${draftId}/ghi-nhan`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
      body: JSON.stringify({ expected_revision: expectedRevision, approval_id: approvalId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Loi ghi nhan ban nhap (${res.status})`);
    }
    return res.json();
  },

  async xuatGoiBanGiao(projectId: string, revision: number, adapterId = "FINAL_CUT_XML"): Promise<GoiBanGiao> {
    const res = await fetch(`${API_BASE}/v1/media/projects/${projectId}/dung/ban-giao`, {
      method: "POST",
      headers: AuthApi.getAuthHeaders(),
      body: JSON.stringify({ revision, adapter_id: adapterId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Loi xuat goi ban giao (${res.status})`);
    }
    return res.json();
  },
};
