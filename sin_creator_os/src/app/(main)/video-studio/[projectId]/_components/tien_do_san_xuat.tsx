"use client";

import * as React from "react";
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Pause,
  Play,
  RotateCcw,
  ShieldAlert,
  Loader2,
  ArrowRight,
  Terminal,
  FileCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export type TrangThaiSanXuat =
  | "DANG_SAN_XUAT"
  | "CHO_TU_LIEU"
  | "CHO_XU_LY_THOI_LUONG"
  | "CHO_LLM"
  | "HOAN_THANH_SAN_XUAT"
  | "DA_TAM_DUNG"
  | "DA_HUY";

export interface BuocSanXuat {
  id: string;
  ten: string;
  moTa: string;
  trangThai: "DANG_XU_LY" | "THANH_CONG" | "LOI" | "CHO";
  thoiGian: string;
  bienNhan?: string;
}

interface TienDoSanXuatProps {
  runId: string;
  trangThaiHienTai: TrangThaiSanXuat;
  onHoanThanh: () => void;
  onThuLai: () => void;
  onHuy: () => void;
}

export function TienDoSanXuat({
  runId,
  trangThaiHienTai: initialStatus,
  onHoanThanh,
  onThuLai,
  onHuy,
}: TienDoSanXuatProps) {
  const [trangThai, setTrangThai] = React.useState<TrangThaiSanXuat>(initialStatus);
  const [buocHienTai, setBuocHienTai] = React.useState<number>(3);
  const [logMessages, setLogMessages] = React.useState<string[]>([
    "[Harness] Khởi tạo phiên sản xuất run_" + runId.substring(0, 8),
    "[StyleLock] Khóa snapshot nhận diện baha_giai_thich_cong_nghe_v1 (Hash: sha256:7f8e...)",
    "[LLM] Đánh giá kịch bản & prompt 12 phân cảnh: HỢP CHUẨN (0 vi phạm nhận diện)",
    "[Voice] Đang sinh giọng đọc Vi-VN Neural TTS cho từng phân cảnh...",
  ]);

  const danhSachBuoc: BuocSanXuat[] = [
    {
      id: "b1",
      ten: "Khóa Phong Cách Kênh (Style Lock)",
      moTa: "Khóa snapshot nhận diện, palette màu, font chữ, voice profile và outro",
      trangThai: "THANH_CONG",
      thoiGian: "0.4s",
      bienNhan: "lock_snap_7f8e3d",
    },
    {
      id: "b2",
      ten: "Thẩm Định Kịch Bản (LLM Preflight)",
      moTa: "Kiểm tra độ phủ luận điểm, quy chuẩn prompt kỹ thuật, chống hallucination",
      trangThai: "THANH_CONG",
      thoiGian: "1.8s",
      bienNhan: "llm_eval_a1b2c3",
    },
    {
      id: "b3",
      ten: "Sinh Giọng Đọc & Căn Phụ Đề (TTS & Alignment)",
      moTa: "Đo thời lượng audio thật từng câu, căn chuẩn timecode < 200ms",
      trangThai: buocHienTai >= 3 ? (buocHienTai > 3 ? "THANH_CONG" : "DANG_XU_LY") : "CHO",
      thoiGian: buocHienTai > 3 ? "4.2s" : "Đang xử lý...",
      bienNhan: "tts_res_9f8e7d",
    },
    {
      id: "b4",
      ten: "Điều Phối Flow & Tạo Tư Liệu (Flow Harness)",
      moTa: "Phát lệnh có biên nhận Harness cho từng shot, cấm gọi trực tiếp bypass",
      trangThai: buocHienTai >= 4 ? (buocHienTai > 4 ? "THANH_CONG" : "DANG_XU_LY") : "CHO",
      thoiGian: buocHienTai > 4 ? "8.5s" : "Chờ bước trước",
      bienNhan: "rcpt_flow_b8a9c0",
    },
    {
      id: "b5",
      ten: "Lắp Ráp & Ghép Dựng Native (FFmpeg CPU)",
      moTa: "Ghép đa track timeline, burn-in subtitle UTF-8, loudnorm -14 LUFS, outro BAHA",
      trangThai: buocHienTai >= 5 ? (buocHienTai > 5 ? "THANH_CONG" : "DANG_XU_LY") : "CHO",
      thoiGian: buocHienTai > 5 ? "6.1s" : "Chờ bước trước",
    },
    {
      id: "b6",
      ten: "Kiểm Định Chất Lượng Tự Động (QC Gate)",
      moTa: "Đo đạc EBU R128 (-14.0 LUFS), Safe zone TikTok, full decode H.264",
      trangThai: buocHienTai >= 6 ? "THANH_CONG" : "CHO",
      thoiGian: buocHienTai >= 6 ? "1.2s" : "Chờ bước trước",
    },
  ];

  // Các nút giả lập trạng thái cho Prototype
  const simulaThanhCong = () => {
    setBuocHienTai(6);
    setTrangThai("HOAN_THANH_SAN_XUAT");
    setLogMessages((prev) => [
      ...prev,
      "[Flow] Tiếp nhận 12 shot hoàn tất (Biên nhận rcpt_flow_b8a9c0)",
      "[FFmpeg] Ghép dựng MP4 dọc 1080x1920 30fps hoàn tất (3.600 frames)",
      "[QC] Kiểm định âm lượng: -14.1 LUFS, True Peak: -1.5 dBTP -> ĐẠT CHUẨN",
      "[Harness] Sản xuất thành công! Chuyển sang màn hình Preview & QC.",
    ]);
  };

  const simulaLoiThoiLuong = () => {
    setTrangThai("CHO_XU_LY_THOI_LUONG");
    setLogMessages((prev) => [
      ...prev,
      "[Cảnh báo] Lời thoại đo được 148.5s, vượt trần 120s (+28.5s) ở chế độ GIU_NGUYEN_LOI.",
      "[Trạng thái] CHO_XU_LY_THOI_LUONG: Cần điều chỉnh lời thoại hoặc tăng thời lượng dự án.",
    ]);
  };

  const simulaThieuRecording = () => {
    setTrangThai("CHO_TU_LIEU");
    setLogMessages((prev) => [
      ...prev,
      "[Blocker] Cảnh c05 & c06 yêu cầu SCREEN_RECORDING thật nhưng chưa có tệp trong kho.",
      "[Trạng thái] CHO_TU_LIEU: Vui lòng tải lên video thao tác màn hình để tiếp tục.",
    ]);
  };

  const simulaLoiLLM = () => {
    setTrangThai("CHO_LLM");
    setLogMessages((prev) => [
      ...prev,
      "[Blocker] Cổng 9Router Gateway timeout (30s) hoặc mô hình AI quá tải.",
      "[Trạng thái] CHO_LLM: Giữ nguyên checkpoint, không fallback prompt thô lách cổng.",
    ]);
  };

  const phanTramHoanThanh = Math.round((buocHienTai / 6) * 100);

  return (
    <div className="flex flex-col gap-6">
      {/* Banner Tiến Độ Tổng Thể */}
      <Card className="p-5 border-primary/20 bg-card flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base">Tiến Độ Sản Xuất Tự Động</span>
              <Badge variant="outline" className="font-mono text-xs">
                Run ID: {runId}
              </Badge>
              {trangThai === "DANG_SAN_XUAT" && (
                <Badge variant="default" className="bg-primary flex items-center gap-1 text-xs">
                  <Loader2 className="size-3 animate-spin" />
                  ĐANG THỰC THI (CONCURRENCY: 1)
                </Badge>
              )}
              {trangThai === "HOAN_THANH_SAN_XUAT" && (
                <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs">
                  <CheckCircle2 className="mr-1 size-3" />
                  HOÀN TẤT 100%
                </Badge>
              )}
              {trangThai.startsWith("CHO_") && (
                <Badge variant="destructive" className="text-xs">
                  <AlertCircle className="mr-1 size-3" />
                  {trangThai}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Dây chuyền thực thi theo luồng bất biến: Lập lịch DAG &rarr; Harness dispatch &rarr; FFmpeg Native render.
            </p>
          </div>

          <div className="text-right">
            <span className="text-2xl font-bold font-mono text-primary">{phanTramHoanThanh}%</span>
            <span className="text-xs text-muted-foreground block">
              Bước {buocHienTai} / 6
            </span>
          </div>
        </div>

        {/* Thanh Progress Bar */}
        <div className="w-full bg-muted rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ${
              trangThai === "HOAN_THANH_SAN_XUAT"
                ? "bg-emerald-500"
                : trangThai.startsWith("CHO_")
                ? "bg-amber-500"
                : "bg-primary"
            }`}
            style={{ width: `${phanTramHoanThanh}%` }}
          />
        </div>
      </Card>

      {/* Danh Sách Các Bước DAG Bền Vững */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 flex flex-col gap-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FileCheck className="size-4 text-primary" />
            Các Bước Thực Thi Dây Chuyền (Durable Steps)
          </h3>

          <div className="flex flex-col gap-2.5">
            {danhSachBuoc.map((b, idx) => (
              <div
                key={b.id}
                className={`p-3.5 rounded-xl border flex items-center justify-between gap-4 transition-colors ${
                  b.trangThai === "THANH_CONG"
                    ? "bg-emerald-500/5 border-emerald-500/20"
                    : b.trangThai === "DANG_XU_LY"
                    ? "bg-primary/5 border-primary/40 shadow-sm"
                    : "bg-card border-border/60 text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="size-7 rounded-full flex items-center justify-center font-bold font-mono text-xs shrink-0">
                    {b.trangThai === "THANH_CONG" ? (
                      <CheckCircle2 className="size-5 text-emerald-500" />
                    ) : b.trangThai === "DANG_XU_LY" ? (
                      <Loader2 className="size-5 text-primary animate-spin" />
                    ) : (
                      <span className="size-6 rounded-full border flex items-center justify-center text-xs">
                        {idx + 1}
                      </span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold truncate text-foreground">{b.ten}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{b.moTa}</p>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-[11px] font-mono block">{b.thoiGian}</span>
                  {b.bienNhan && (
                    <span className="text-[10px] font-mono text-primary bg-primary/10 px-1 py-0.5 rounded">
                      {b.bienNhan}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cột Phải: Nhật Ký Thực Thi (Log Feed) & Điều Khiển Giả Lập Prototype */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* Hộp Log Terminal Chuẩn */}
          <Card className="p-4 bg-muted/40 font-mono text-xs flex flex-col gap-2 max-h-[320px] overflow-hidden">
            <div className="flex items-center justify-between border-b pb-2 text-muted-foreground">
              <span className="flex items-center gap-1.5 font-semibold">
                <Terminal className="size-3.5 text-primary" />
                Nhật Ký Thực Thi (Audit Log)
              </span>
              <span className="text-[10px]">Harness Concurrency: 1</span>
            </div>
            <div className="flex flex-col gap-1.5 overflow-y-auto pr-1 text-[11px] leading-relaxed">
              {logMessages.map((log, i) => (
                <div key={i} className="text-muted-foreground">
                  {log}
                </div>
              ))}
            </div>
          </Card>

          {/* Hộp Thao Tác Mô Phỏng Prototype (Chỉ Dành Cho Review Prototype) */}
          <Card className="p-4 border-dashed border-primary/40 bg-primary/5 flex flex-col gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
              <ShieldAlert className="size-3.5" />
              Công Cụ Kiểm Thử Trạng Thái Prototype (G1)
            </span>
            <p className="text-[11px] text-muted-foreground">
              Bấm để mô phỏng các tình huống thực tế của dây chuyền trước khi nghiệm thu:
            </p>

            <div className="grid grid-cols-2 gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={simulaThanhCong}
                className="text-xs bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
              >
                Mô phỏng: Hoàn tất 100%
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={simulaLoiThoiLuong}
                className="text-xs bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300"
              >
                Mô phỏng: Lệch thời lượng
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={simulaThieuRecording}
                className="text-xs"
              >
                Mô phỏng: Thiếu tư liệu
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={simulaLoiLLM}
                className="text-xs"
              >
                Mô phỏng: Timeout LLM
              </Button>
            </div>

            {trangThai === "HOAN_THANH_SAN_XUAT" && (
              <Button
                type="button"
                size="sm"
                onClick={onHoanThanh}
                className="w-full mt-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
              >
                Xem Trước & Kiểm Định QC Video (Bước Tiếp Theo)
                <ArrowRight className="ml-1.5 size-4" />
              </Button>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
