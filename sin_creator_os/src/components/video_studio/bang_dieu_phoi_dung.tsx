"use client";

import React, { useState } from "react";
import {
  Play,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  Layers,
  Scissors,
  FileCode,
  Share2,
  ExternalLink,
  Sliders,
  Volume2,
  Type
} from "lucide-react";
import { boDieuPhoiDungApi, DinhDanhPhien, CheckpointPhien, BanNhapDung } from "@/lib/api/bo_dieu_phoi_dung_api";

interface BangDieuPhoiDungProps {
  projectId: string;
  currentRevision: number;
  timelineDoc: Record<string, unknown>;
  onTimelineUpdate?: () => void;
}

export function BangDieuPhoiDung({
  projectId,
  currentRevision,
  timelineDoc,
  onTimelineUpdate,
}: BangDieuPhoiDungProps) {
  const [activePhien, setActivePhien] = useState<DinhDanhPhien | null>(null);
  const [activeDraft, setActiveDraft] = useState<BanNhapDung | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleKhoiTaoPhien = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const phien = await boDieuPhoiDungApi.taoPhien(projectId, currentRevision, "hash_baseline");
      setActivePhien(phien);
      const draft = await boDieuPhoiDungApi.taoBanNhap(projectId, phien.run_id, timelineDoc);
      setActiveDraft(draft);
      setMessage(`Khoi tao phien dieu phoi ${phien.run_id} thanh cong voi Ban nhap revision ${draft.draft_revision}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Loi khoi tao phien dieu phoi");
    } finally {
      setLoading(false);
    }
  };

  const handleXuatNLE = async () => {
    setLoading(true);
    setError(null);
    try {
      const bundle = await boDieuPhoiDungApi.xuatGoiBanGiao(projectId, currentRevision, "FINAL_CUT_XML");
      setMessage(`Da xuat goi ban giao NLE: ${bundle.bundle_id} voi ${bundle.files.length} tep.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Loi xuat goi ban giao NLE");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4 text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-indigo-400" />
          <h3 className="font-semibold text-base text-white">Bang Dieu Phoi Dung Video Chuyen Nghiep</h3>
          <span className="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
            Harness V1
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!activePhien ? (
            <button
              onClick={handleKhoiTaoPhien}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition"
            >
              <Play className="w-3.5 h-3.5" />
              Khoi Tao Phien Dieu Phoi
            </button>
          ) : (
            <button
              onClick={() => {
                setActivePhien(null);
                setActiveDraft(null);
                setMessage("Da dong phien dieu phoi.");
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Dong Phien
            </button>
          )}

          <button
            onClick={handleXuatNLE}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition"
          >
            <Share2 className="w-3.5 h-3.5" />
            Xuat Goi NLE (XML)
          </button>
        </div>
      </div>

      {message && (
        <div className="flex items-center gap-2 p-3 bg-indigo-950/60 border border-indigo-800 text-indigo-200 text-xs rounded-lg">
          <CheckCircle className="w-4 h-4 text-indigo-400 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 p-3 bg-rose-950/60 border border-rose-800 text-rose-200 text-xs rounded-lg">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {activePhien && activeDraft ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-3 space-y-1.5 text-xs">
            <span className="text-slate-400 block font-medium">Thong Tin Phien Chay (Run)</span>
            <div className="text-slate-200 font-mono truncate">{activePhien.run_id}</div>
            <div className="text-slate-400">Actor: <span className="text-slate-200">{activePhien.actor_id}</span></div>
            <div className="text-slate-400">Chinh sach: <span className="text-slate-200">{activePhien.policy_version}</span></div>
          </div>

          <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-3 space-y-1.5 text-xs">
            <span className="text-slate-400 block font-medium">Trang Thai Ban Nhap (Draft)</span>
            <div className="text-slate-200 font-mono truncate">{activeDraft.draft_id}</div>
            <div className="text-slate-400">Revision: <span className="text-emerald-400 font-bold">{activeDraft.draft_revision}</span> (Goc: rev {activeDraft.base_revision})</div>
            <div className="text-slate-400">Khoa: <span className={activeDraft.is_locked ? "text-rose-400 font-bold" : "text-emerald-400"}>{activeDraft.is_locked ? "Da Khoa" : "Mo Ghi"}</span></div>
          </div>

          <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-3 space-y-2 text-xs flex flex-col justify-between">
            <div>
              <span className="text-slate-400 block font-medium">Che Do Project</span>
              <div className="text-slate-200 flex items-center gap-1.5 font-semibold mt-1">
                <FileCode className="w-4 h-4 text-indigo-400" />
                CANONICAL (SSOT)
              </div>
            </div>
            <span className="text-[11px] text-slate-400">Mo hinh 1 ben ghi tai 1 thoi diem, kiem soat dong thoi CAS/OCC 409.</span>
          </div>
        </div>
      ) : (
        <div className="text-center py-6 bg-slate-950/40 border border-dashed border-slate-800 rounded-lg space-y-2">
          <Layers className="w-8 h-8 text-slate-600 mx-auto" />
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Chua co phien dieu phoi hoat dong. Nhan <b>Khoi Tao Phien Dieu Phoi</b> de Agent tao ban nhap doc lap, kiem soat thao tac nguyen tu va bao toan timeline chinh.
          </p>
        </div>
      )}
    </div>
  );
}
