"use client";

import * as React from "react";
import {
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
  Edit3,
  AlertTriangle,
  Film,
  Mic,
  Video,
  FileCode,
  ShieldCheck,
  ChevronRight,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export interface ShotMẫu {
  shotId: string;
  loaiShot: "DIAGRAM" | "SCREEN_RECORDING" | "AI_VIDEO" | "TEXT_MOTION" | "BRAND_OUTRO";
  thoiLuongGiay: number;
  soFrame: number;
  promptKyThuat: string;
  promptPhuDinh: string;
  tuLieuNguon: string;
  trangThaiTuLieu: "SAN_SANG" | "CHO_FLOW" | "CHO_RECORDING" | "DO_HOA_SVG";
}

export interface CanhMẫu {
  canhId: string;
  thuTu: number;
  tieuDe: string;
  loaiCanh: "HOOK" | "DIAGRAM" | "SCREEN_RECORDING" | "AI_VIDEO" | "TEXT_MOTION" | "BRAND_OUTRO";
  thoiGianBatDau: number;
  thoiGianKetThuc: number;
  loiThoai: string;
  chuManHinh: string;
  shots: ShotMẫu[];
}

export interface KeHoachMẫu {
  keHoachId: string;
  revision: number;
  tongThoiLuongGiay: number;
  tongFrame: number;
  fps: number;
  tyLeKhungHinh: string;
  styleSnapshotHash: string;
  uocTinhChiPhi: string;
  danhSachCanh: CanhMẫu[];
}

interface DuyetPhanCanhProps {
  keHoach: KeHoachMẫu;
  onDuyetKeHoach: (keHoachDaSua: KeHoachMẫu) => void;
  onQuayLai: () => void;
}

export function DuyetPhanCanh({ keHoach, onDuyetKeHoach, onQuayLai }: DuyetPhanCanhProps) {
  const [danhSachCanh, setDanhSachCanh] = React.useState<CanhMẫu[]>(keHoach.danhSachCanh);
  const [canhDangChon, setCanhDangChon] = React.useState<string>(keHoach.danhSachCanh[0]?.canhId || "c01");
  const [isEditing, setIsEditing] = React.useState(false);

  const selectedScene = danhSachCanh.find((c) => c.canhId === canhDangChon) || danhSachCanh[0];

  const handleUpdateLoiThoai = (canhId: string, text: string) => {
    setDanhSachCanh((prev) =>
      prev.map((c) => (c.canhId === canhId ? { ...c, loiThoai: text } : c))
    );
  };

  const handleUpdatePromptShot = (canhId: string, shotId: string, prompt: string) => {
    setDanhSachCanh((prev) =>
      prev.map((c) => {
        if (c.canhId !== canhId) return c;
        return {
          ...c,
          shots: c.shots.map((s) => (s.shotId === shotId ? { ...s, promptKyThuat: prompt } : s)),
        };
      })
    );
  };

  const tongSoShot = danhSachCanh.reduce((acc, c) => acc + c.shots.length, 0);

  return (
    <div className="flex flex-col gap-6">
      {/* Thanh Chỉ Số Kế Hoạch & Tính Khung Hình */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-3 flex flex-col gap-1 border-primary/20 bg-card">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Thời lượng & Frame
          </span>
          <div className="text-xl font-bold font-mono text-primary">
            {keHoach.tongThoiLuongGiay}s / {keHoach.tongFrame} F
          </div>
          <span className="text-[11px] text-muted-foreground">30 fps CFR chuẩn TikTok</span>
        </Card>

        <Card className="p-3 flex flex-col gap-1 border-primary/20 bg-card">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Quy mô phân cảnh
          </span>
          <div className="text-xl font-bold font-mono">
            {danhSachCanh.length} Cảnh / {tongSoShot} Shot
          </div>
          <span className="text-[11px] text-muted-foreground">Phân bổ đều luận điểm</span>
        </Card>

        <Card className="p-3 flex flex-col gap-1 border-primary/20 bg-card">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Ước tính chi phí AI
          </span>
          <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {keHoach.uocTinhChiPhi}
          </div>
          <span className="text-[11px] text-muted-foreground">Budget Guard đã cấp</span>
        </Card>

        <Card className="p-3 flex flex-col gap-1 border-primary/20 bg-card">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Phiên bản kế hoạch
          </span>
          <div className="text-xl font-bold font-mono flex items-center gap-1.5">
            Rev #{keHoach.revision}
            <Badge variant="outline" className="text-[10px] py-0">CAS-LOCKED</Badge>
          </div>
          <span className="text-[11px] text-muted-foreground truncate" title={keHoach.styleSnapshotHash}>
            Hash: {keHoach.styleSnapshotHash.substring(0, 16)}...
          </span>
        </Card>
      </div>

      {/* Bố Cục Duyệt Storyboard: Danh Sách Cảnh + Chi Tiết Prompt Từng Shot */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Cột 1: Danh sách các phân cảnh (Storyboard Scenes) */}
        <div className="lg:col-span-5 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Film className="size-4 text-primary" />
              Danh Sách Phân Cảnh ({danhSachCanh.length})
            </h3>
            <span className="text-xs text-muted-foreground">Bấm chọn cảnh để xem/sửa</span>
          </div>

          <div className="flex flex-col gap-2 max-h-[620px] overflow-y-auto pr-1">
            {danhSachCanh.map((canh) => {
              const isActive = canh.canhId === canhDangChon;
              return (
                <div
                  key={canh.canhId}
                  onClick={() => setCanhDangChon(canh.canhId)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    isActive
                      ? "border-primary bg-primary/5 shadow-sm ring-1 ring-primary"
                      : "border-border bg-card hover:bg-muted/40"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold font-mono bg-muted px-1.5 py-0.5 rounded text-[11px]">
                        {canh.canhId}
                      </span>
                      <span className="font-semibold truncate max-w-[170px]">{canh.tieuDe}</span>
                    </div>
                    <Badge variant="secondary" className="font-mono text-[10px]">
                      {canh.thoiGianBatDau}s - {canh.thoiGianKetThuc}s ({canh.thoiGianKetThuc - canh.thoiGianBatDau}s)
                    </Badge>
                  </div>

                  <p className="text-xs text-muted-foreground line-clamp-2 italic mb-2">
                    &ldquo;{canh.loiThoai}&rdquo;
                  </p>

                  <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-border/50">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Layers className="size-3" />
                      {canh.shots.length} shot
                    </span>
                    <Badge variant="outline" className="text-[10px] py-0 border-primary/30 text-primary">
                      {canh.loaiCanh}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Cột 2: Thanh Kiểm Tra & Chi Tiết Prompt Từng Shot Của Cảnh Được Chọn */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <Card className="p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="font-bold text-base">{selectedScene.tieuDe}</h4>
                  <Badge variant="default" className="text-xs">
                    {selectedScene.canhId}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Thời lượng phân cảnh: {selectedScene.thoiGianBatDau}s đến {selectedScene.thoiGianKetThuc}s (
                  {(selectedScene.thoiGianKetThuc - selectedScene.thoiGianBatDau) * 30} frames)
                </p>
              </div>

              <Badge variant="outline" className="font-mono text-xs text-primary border-primary/30">
                Loại: {selectedScene.loaiCanh}
              </Badge>
            </div>

            {/* Lời thoại giọng đọc của cảnh */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground">
                <Mic className="size-3.5 text-primary" />
                Lời thoại phân cảnh (Căn phụ đề & Giọng đọc Vi-VN)
              </label>
              <textarea
                rows={3}
                value={selectedScene.loiThoai}
                onChange={(e) => handleUpdateLoiThoai(selectedScene.canhId, e.target.value)}
                className="w-full resize-y rounded-lg border bg-background p-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Chữ hiển thị nổi trên màn hình (Safe Zone Overlay) */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                Tiêu đề / Chữ hiển thị trên màn hình
              </label>
              <Input
                value={selectedScene.chuManHinh}
                onChange={(e) => {
                  const val = e.target.value;
                  setDanhSachCanh((prev) =>
                    prev.map((c) => (c.canhId === selectedScene.canhId ? { ...c, chuManHinh: val } : c))
                  );
                }}
                className="text-xs font-mono"
              />
            </div>

            {/* Chi tiết từng Shot kỹ thuật */}
            <div className="flex flex-col gap-3 pt-2 border-t">
              <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Biên Dịch Prompt Kỹ Thuật Từng Shot ({selectedScene.shots.length})
              </span>

              <div className="flex flex-col gap-3">
                {selectedScene.shots.map((shot, idx) => (
                  <div key={shot.shotId} className="rounded-lg border bg-muted/20 p-3.5 flex flex-col gap-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-primary">Shot #{idx + 1} ({shot.shotId})</span>
                        <Badge variant="outline" className="text-[10px] py-0">
                          {shot.loaiShot}
                        </Badge>
                      </div>
                      <span className="font-mono text-muted-foreground text-[11px]">
                        {shot.thoiLuongGiay}s ({shot.soFrame} frames)
                      </span>
                    </div>

                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted-foreground">
                        Prompt Kỹ Thuật (Harness Verified):
                      </span>
                      <textarea
                        rows={3}
                        value={shot.promptKyThuat}
                        onChange={(e) => handleUpdatePromptShot(selectedScene.canhId, shot.shotId, e.target.value)}
                        className="w-full resize-y rounded border bg-background p-2 font-mono text-xs leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-muted-foreground pt-1">
                      <div>
                        <span className="font-semibold block">Tư liệu nguồn:</span>
                        <span className="truncate block font-mono">{shot.tuLieuNguon}</span>
                      </div>
                      <div>
                        <span className="font-semibold block">Trạng thái tư liệu:</span>
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                          {shot.trangThaiTuLieu}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Nút hành động duyệt kế hoạch */}
          <div className="flex items-center justify-between pt-2">
            <Button type="button" variant="outline" onClick={onQuayLai}>
              Quay Lại Nhập Nội Dung
            </Button>
            <Button
              type="button"
              size="lg"
              onClick={() => onDuyetKeHoach({ ...keHoach, danhSachCanh })}
              className="bg-primary font-medium"
            >
              <ShieldCheck className="mr-2 size-4" />
              Duyệt Kế Hoạch & Tiến Hành Sản Xuất Video
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
