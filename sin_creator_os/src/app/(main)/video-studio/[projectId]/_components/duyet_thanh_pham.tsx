"use client";

import * as React from "react";
import {
  Play,
  Pause,
  Download,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Sliders,
  Volume2,
  VolumeX,
  ShieldCheck,
  FileText,
  FileCode,
  Share2,
  Layers,
  Sparkles,
  Maximize2,
  ExternalLink,
  Edit,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface DuyetThanhPhamProps {
  runId: string;
  tongThoiLuongGiay: number;
  onSuaMotCanh: (canhId: string, noiDungMoi: string) => void;
  onLamMoi: () => void;
}

export function DuyetThanhPham({
  runId,
  tongThoiLuongGiay,
  onSuaMotCanh,
  onLamMoi,
}: DuyetThanhPhamProps) {
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(0);
  const [isMuted, setIsMuted] = React.useState(false);
  const [showSafeZone, setShowSafeZone] = React.useState(true);
  const [canhDangSua, setCanhDangSua] = React.useState<string | null>(null);
  const [promptCanhSua, setPromptCanhSua] = React.useState("");
  const [showDownloadModal, setShowDownloadModal] = React.useState(false);
  const [singleSceneEditSuccess, setSingleSceneEditSuccess] = React.useState(false);

  // Giả lập tiến trình phát video
  React.useEffect(() => {
    let timer: any;
    if (isPlaying) {
      timer = setInterval(() => {
        setCurrentTime((prev) => {
          if (prev >= tongThoiLuongGiay) {
            setIsPlaying(false);
            return 0;
          }
          return prev + 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPlaying, tongThoiLuongGiay]);

  const handleOpenSuaCanh = (canhId: string, promptHienTai: string) => {
    setCanhDangSua(canhId);
    setPromptCanhSua(promptHienTai);
    setSingleSceneEditSuccess(false);
  };

  const handleLuuSuaCanh = () => {
    if (canhDangSua) {
      onSuaMotCanh(canhDangSua, promptCanhSua);
      setSingleSceneEditSuccess(true);
      setTimeout(() => {
        setCanhDangSua(null);
        setSingleSceneEditSuccess(false);
      }, 1200);
    }
  };

  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Thanh Thông Báo Kết Quả Kiểm Định QC */}
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-emerald-500/20 p-2 text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="size-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">Báo Cáo Kiểm Định Chất Lượng (Automated QC):</span>
              <Badge variant="secondary" className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-mono text-xs">
                5/5 TIÊU CHÍ ĐẠT
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 font-mono">
              Âm lượng: -14.1 LUFS (±1 LUFS) &bull; True Peak: -1.5 dBTP &bull; Khung hình: 1080x1920 30fps CFR
              &bull; TikTok Safe Zone: PASS
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => setShowDownloadModal(true)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs"
          >
            <Download className="mr-1.5 size-4" />
            Tải Gói Video & Tài Sản Hoàn Chỉnh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Cột 1: Trình Phát Video Dọc 9:16 Với TikTok Safe Zone Overlay */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="relative w-full max-w-[340px] aspect-[9/16] rounded-2xl overflow-hidden border-2 border-border bg-black shadow-2xl flex flex-col justify-between p-4">
            {/* Lớp Safe Zone Overlay (150px trên, 320px dưới, 120px phải, 60px trái) */}
            {showSafeZone && (
              <div className="absolute inset-0 pointer-events-none z-20 flex flex-col justify-between border-dashed border-amber-500/60 m-3 rounded-lg">
                <div className="h-10 bg-amber-500/10 border-b border-amber-500/40 text-[10px] text-amber-500 flex items-center justify-center font-mono">
                  Safe Zone: Mép trên (150px)
                </div>
                <div className="flex-1 flex justify-end pr-2 items-center">
                  <div className="w-16 h-36 bg-amber-500/10 border border-amber-500/40 rounded text-[9px] text-amber-500 flex flex-col items-center justify-center text-center p-1 font-mono">
                    Vùng nút tương tác TikTok
                  </div>
                </div>
                <div className="h-16 bg-amber-500/10 border-t border-amber-500/40 text-[10px] text-amber-500 flex items-center justify-center font-mono">
                  Vùng mô tả & Caption TikTok (320px)
                </div>
              </div>
            )}

            {/* Khung Hình Video Mô Phỏng */}
            <div className="absolute inset-0 z-0 bg-gradient-to-b from-slate-900 via-indigo-950 to-slate-950 flex flex-col items-center justify-center p-6 text-center">
              <div className="size-16 rounded-2xl bg-primary/20 border border-primary/40 flex items-center justify-center mb-4 text-primary">
                <Sparkles className="size-8" />
              </div>
              <Badge variant="outline" className="mb-2 text-primary border-primary/40 font-mono text-xs">
                BAHA Creator Studio v2.0
              </Badge>
              <h4 className="text-white font-bold text-lg leading-tight mb-2">
                RAG vs Fine-tuning: Kiến Trúc Nào Cho Doanh Nghiệp?
              </h4>
              <p className="text-slate-300 text-xs italic">
                Cảnh hiện tại ({formatTime(currentTime)} / {formatTime(tongThoiLuongGiay)})
              </p>

              {/* Subtitle mô phỏng chuẩn TikTok Safe Zone */}
              <div className="absolute bottom-20 left-4 right-4 z-10 text-center">
                <span className="bg-black/80 text-white font-semibold text-xs px-2.5 py-1.5 rounded-md leading-relaxed inline-block shadow">
                  RAG giúp truy xuất dữ liệu nội bộ tức thì mà không cần huấn luyện lại toàn bộ mô hình lớn.
                </span>
              </div>
            </div>

            {/* Bộ Điều Khiển Phát Nhanh Trên Player */}
            <div className="relative z-30 mt-auto flex items-center justify-between bg-black/60 backdrop-blur rounded-xl p-2 text-white">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setIsPlaying(!isPlaying)}
                className="text-white hover:bg-white/20 size-8"
              >
                {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
              </Button>

              <span className="font-mono text-xs">
                {formatTime(currentTime)} / {formatTime(tongThoiLuongGiay)}
              </span>

              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setIsMuted(!isMuted)}
                className="text-white hover:bg-white/20 size-8"
              >
                {isMuted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-3 mt-3">
            <label className="text-xs font-medium flex items-center gap-1.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showSafeZone}
                onChange={(e) => setShowSafeZone(e.target.checked)}
                className="rounded"
              />
              Bật Safe Zone TikTok (1080x1920)
            </label>
          </div>
        </div>

        {/* Cột 2: Danh Sách Phân Cảnh & Thao Tác Sửa Cục Bộ 1 Cảnh */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <Card className="p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="font-bold text-sm flex items-center gap-2">
                  <Sliders className="size-4 text-primary" />
                  Sửa Cục Bộ Phân Cảnh (Scoped Re-render)
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Thay đổi một cảnh mà không làm ảnh hưởng đến hash tư liệu các cảnh khác trong video.
                </p>
              </div>

              <Badge variant="outline" className="text-xs font-mono">
                12 Cảnh / 3.600 frames
              </Badge>
            </div>

            <div className="flex flex-col gap-2.5 max-h-[460px] overflow-y-auto pr-1">
              {[
                { id: "c01", time: "0-3s", type: "HOOK", title: "Đặt vấn đề: Khi nào dùng RAG?", prompt: "Hook mở đầu trực diện, văn bản chữ động tương phản cao" },
                { id: "c02", time: "3-13s", type: "DIAGRAM", title: "Bản chất RAG (Retrieval-Augmented)", prompt: "Sơ đồ kiến trúc Vector DB kết nối LLM" },
                { id: "c03", time: "13-23s", type: "DIAGRAM", title: "Bản chất Fine-tuning", prompt: "Sơ đồ cập nhật trọng số mô hình qua tập dữ liệu domain" },
                { id: "c05", time: "35-47s", type: "SCREEN_RECORDING", title: "Demo RAG truy xuất tài liệu thực tế", prompt: "Thao tác tìm kiếm tài liệu nội bộ trên giao diện enterprise" },
                { id: "c08", time: "71-83s", type: "AI_VIDEO", title: "Minh họa bối cảnh doanh nghiệp vận hành", prompt: "Không gian làm việc công nghệ hiện đại, đội ngũ kỹ sư tối ưu pipeline" },
                { id: "c12", time: "115-120s", type: "BRAND_OUTRO", title: "Brand Outro BAHA Group (O1)", prompt: "Logo BAHA Group + Slogan cung cấp giải pháp AI toàn diện" },
              ].map((c) => (
                <div
                  key={c.id}
                  className="p-3 rounded-lg border bg-muted/20 flex items-center justify-between gap-3 text-xs"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold font-mono bg-muted px-1.5 py-0.5 rounded text-[11px] text-primary">
                        {c.id}
                      </span>
                      <span className="font-semibold truncate">{c.title}</span>
                      <Badge variant="outline" className="text-[10px] py-0">
                        {c.time}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-muted-foreground truncate font-mono">
                      {c.prompt}
                    </p>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenSuaCanh(c.id, c.prompt)}
                    className="shrink-0 text-xs"
                  >
                    <Edit className="mr-1 size-3" />
                    Sửa Cảnh Này
                  </Button>
                </div>
              ))}
            </div>
          </Card>

          <div className="flex items-center justify-between pt-2">
            <Button type="button" variant="outline" onClick={onLamMoi}>
              <RotateCcw className="mr-1.5 size-4" />
              Tạo Video Mới Khác
            </Button>
            <Button
              type="button"
              size="lg"
              onClick={() => setShowDownloadModal(true)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
            >
              <Download className="mr-2 size-4" />
              Tải Gói Xuất Bản Hoàn Chỉnh
            </Button>
          </div>
        </div>
      </div>

      {/* Modal Sửa Cục Bộ 1 Cảnh */}
      <Dialog open={!!canhDangSua} onOpenChange={() => setCanhDangSua(null)}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Sửa Cục Bộ Phân Cảnh ({canhDangSua})</DialogTitle>
            <DialogDescription>
              Hệ thống sẽ chỉ tái biên dịch và sinh lại riêng phân cảnh này. Các phân cảnh khác được giữ nguyên 100% hash tư liệu.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-3 py-2">
            <label className="text-xs font-semibold text-muted-foreground">
              Prompt kỹ thuật phân cảnh mới:
            </label>
            <textarea
              rows={4}
              value={promptCanhSua}
              onChange={(e) => setPromptCanhSua(e.target.value)}
              className="w-full resize-y rounded-lg border bg-background p-2.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
            />
            {singleSceneEditSuccess && (
              <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-2 text-xs text-emerald-600 flex items-center gap-1.5">
                <CheckCircle2 className="size-4 shrink-0" />
                Đã cập nhật phân cảnh {canhDangSua}! Hash các cảnh khác được bảo toàn nguyên vẹn.
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCanhDangSua(null)}>
              Hủy
            </Button>
            <Button type="button" onClick={handleLuuSuaCanh} className="bg-primary">
              Lưu & Tái Dựng Cảnh Này
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Tải Gói Xuất Bản Hoàn Chỉnh */}
      <Dialog open={showDownloadModal} onOpenChange={setShowDownloadModal}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Download className="size-5 text-emerald-500" />
              Gói Video Thành Phẩm & Hồ Sơ Xuất Bản
            </DialogTitle>
            <DialogDescription>
              Trọn bộ tệp tài sản đã được kiểm định EBU R128 (-14.1 LUFS) và khóa mã băm SHA-256 nguyên tử.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-2.5 py-3">
            {[
              { ten: "video_thanh_pham_120s.mp4", moTa: "Video dọc 1080x1920, 30fps CFR, H.264 + AAC", kichThuoc: "28.4 MB" },
              { ten: "phu_de_tieng_viet.srt", moTa: "Phụ đề UTF-8 chuẩn Safe Zone TikTok, sai lệch < 200ms", kichThuoc: "4.2 KB" },
              { ten: "kich_ban_va_storyboard.json", moTa: "Kịch bản, phân cảnh và prompt kỹ thuật từng shot", kichThuoc: "12.8 KB" },
              { ten: "du_an_timeline.json", moTa: "Tệp dự án chỉnh sửa lại (FCPXML/Native Timeline V2)", kichThuoc: "34.1 KB" },
              { ten: "bao_cao_kiem_dinh_qc.json", moTa: "Số đo EBU R128 (-14.1 LUFS), True Peak, Safe zone", kichThuoc: "5.6 KB" },
              { ten: "package_manifest.json", moTa: "Bảng kê chứng thực mã SHA-256 toàn bộ gói tài sản", kichThuoc: "3.1 KB" },
            ].map((f, i) => (
              <div key={i} className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20 text-xs">
                <div>
                  <span className="font-semibold font-mono block text-foreground">{f.ten}</span>
                  <span className="text-[11px] text-muted-foreground">{f.moTa}</span>
                </div>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {f.kichThuoc}
                </Badge>
              </div>
            ))}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setShowDownloadModal(false)}>
              Đóng
            </Button>
            <Button
              type="button"
              onClick={() => {
                setShowDownloadModal(false);
                alert("Bắt đầu tải xuống gói tài sản ZIP (28.5 MB)...");
              }}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Tải Xuống Trọn Gói (.ZIP)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
