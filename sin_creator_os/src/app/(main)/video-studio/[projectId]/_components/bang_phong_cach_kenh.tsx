"use client";

import * as React from "react";
import {
  Lock,
  CheckCircle2,
  Palette,
  Type,
  Mic,
  ShieldAlert,
  Layers,
  Image as ImageIcon,
  Sparkles,
  Volume2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function BangPhongCachKenh() {
  return (
    <div className="flex flex-col gap-6">
      {/* Header Thông Tin Style Family Đã Khóa */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm">Hồ Sơ Phong Cách Công Ty & Kênh:</span>
            <Badge variant="default" className="font-mono text-xs">
              baha_giai_thich_cong_nghe_v1
            </Badge>
            <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs">
              <CheckCircle2 className="mr-1 size-3" />
              ĐÃ DUYỆT BẤT BIẾN
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Gắn với kênh TikTok <code className="font-mono">tiktok_tiktok</code> &bull; Snapshot Hash:{" "}
            <code className="font-mono">sha256:7f8e3d2a1b9c4f5e6a0b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f</code>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
          <span>Phiên bản: 1.0.0</span>
          <span>&bull;</span>
          <span>Hiệu lực: Toàn bộ run sản xuất</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Khối 1: Logo & Nhận Diện Thương Hiệu */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 border-b pb-2">
            <div className="rounded bg-primary/10 p-1 text-primary">
              <ImageIcon className="size-4" />
            </div>
            <h4 className="font-bold text-xs uppercase tracking-wider">Logo & Nhận Diện</h4>
          </div>

          <div className="flex items-center gap-3 bg-muted/20 p-3 rounded-lg">
            <img
              src="/logo.png"
              alt="BAHA Logo"
              className="size-12 object-contain bg-background rounded-lg border p-1"
            />
            <div className="text-xs min-w-0">
              <p className="font-semibold truncate">BAHA Group Logo Chuẩn</p>
              <p className="text-[11px] text-muted-foreground font-mono">1200x1382 RGBA (822 KB)</p>
              <Badge variant="outline" className="text-[9px] mt-1 py-0">
                Clear space: 24px
              </Badge>
            </div>
          </div>

          <ul className="text-[11px] text-muted-foreground space-y-1 list-disc pl-4">
            <li>Vị trí chuẩn: Góc trên bên trái trong TikTok Safe Zone.</li>
            <li>Kích thước tối thiểu: 48x48px (độ phân giải 1080x1920).</li>
            <li>Quy tắc bất biến: Tuyệt đối không để AI vẽ lại logo trong video.</li>
          </ul>
        </Card>

        {/* Khối 2: Bảng Màu Ngữ Nghĩa (Semantic Palette) */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 border-b pb-2">
            <div className="rounded bg-primary/10 p-1 text-primary">
              <Palette className="size-4" />
            </div>
            <h4 className="font-bold text-xs uppercase tracking-wider">Bảng Màu Ngữ Nghĩa</h4>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            {[
              { ten: "Primary", mau: "#1e3a8a", code: "#1e3a8a" },
              { ten: "Accent", mau: "#2563eb", code: "#2563eb" },
              { ten: "Background Dark", mau: "#0f172a", code: "#0f172a" },
              { ten: "Text Light", mau: "#f8fafc", code: "#f8fafc" },
              { ten: "Emphasis Cyan", mau: "#38bdf8", code: "#38bdf8" },
              { ten: "Success", mau: "#10b981", code: "#10b981" },
            ].map((p, i) => (
              <div key={i} className="flex items-center gap-2 p-1.5 rounded border bg-muted/20">
                <div
                  className="size-4 rounded-full border shadow-sm shrink-0"
                  style={{ backgroundColor: p.mau }}
                />
                <div className="min-w-0 truncate">
                  <span className="text-[10px] block text-muted-foreground">{p.ten}</span>
                  <span className="text-[11px] font-bold">{p.code}</span>
                </div>
              </div>
            ))}
          </div>

          <p className="text-[11px] text-muted-foreground">
            Độ tương phản chữ/nền: Đạt chuẩn WCAG AAA (&gt; 7:1) trên mọi khung hình.
          </p>
        </Card>

        {/* Khối 3: Giọng Đọc & Phát Âm Thuật Ngữ */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 border-b pb-2">
            <div className="rounded bg-primary/10 p-1 text-primary">
              <Mic className="size-4" />
            </div>
            <h4 className="font-bold text-xs uppercase tracking-wider">Giọng Đọc & Phát Âm</h4>
          </div>

          <div className="flex flex-col gap-1.5 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Giọng đọc chuẩn:</span>
              <span className="font-semibold font-mono">Vi-VN Neural TTS (Nữ/Nam trung tính)</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Tốc độ & Tone:</span>
              <span className="font-mono">1.0x (140-160 từ/phút) &bull; Neutral</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Chuẩn âm thanh:</span>
              <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                -14 LUFS (±1 LUFS)
              </span>
            </div>
          </div>

          <div className="rounded border bg-muted/20 p-2 text-[11px]">
            <span className="font-semibold block mb-1">Từ điển thuật ngữ AI đã khóa:</span>
            <div className="grid grid-cols-2 gap-1 font-mono text-[10px]">
              <span>RAG &rarr; R-A-G</span>
              <span>MCP &rarr; M-C-P</span>
              <span>API &rarr; A-P-I</span>
              <span>LLM &rarr; L-L-M</span>
            </div>
          </div>
        </Card>

        {/* Khối 4: Phông Chữ & Quy Chuẩn Phụ Đề */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 border-b pb-2">
            <div className="rounded bg-primary/10 p-1 text-primary">
              <Type className="size-4" />
            </div>
            <h4 className="font-bold text-xs uppercase tracking-wider">Phông Chữ & Phụ Đề</h4>
          </div>

          <div className="flex flex-col gap-1.5 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Họ phông chính:</span>
              <span className="font-semibold font-mono">Arial / System Sans-serif</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Hỗ trợ tiếng Việt:</span>
              <span className="font-semibold text-emerald-600">100% UTF-8 (Không lỗi dấu)</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Quy cách phụ đề:</span>
              <span className="font-mono">Tối đa 2 dòng / 38 ký tự</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Tốc độ đọc:</span>
              <span className="font-mono">&le; 20 ký tự / giây</span>
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground">
            Phụ đề burn-in bằng FFmpeg CPU, có viền đen nhẹ chống chìm chữ trên nền sáng.
          </p>
        </Card>

        {/* Khối 5: Vùng An Toàn TikTok Safe Zone */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 border-b pb-2">
            <div className="rounded bg-primary/10 p-1 text-primary">
              <Layers className="size-4" />
            </div>
            <h4 className="font-bold text-xs uppercase tracking-wider">TikTok Safe Zone (9:16)</h4>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 rounded border bg-muted/20">
              <span className="text-[10px] text-muted-foreground block">Mép Trên:</span>
              <span className="font-bold text-primary">150 px</span>
            </div>
            <div className="p-2 rounded border bg-muted/20">
              <span className="text-[10px] text-muted-foreground block">Mép Dưới:</span>
              <span className="font-bold text-primary">320 px</span>
            </div>
            <div className="p-2 rounded border bg-muted/20">
              <span className="text-[10px] text-muted-foreground block">Mép Phải:</span>
              <span className="font-bold text-primary">120 px</span>
            </div>
            <div className="p-2 rounded border bg-muted/20">
              <span className="text-[10px] text-muted-foreground block">Mép Trái:</span>
              <span className="font-bold text-primary">60 px</span>
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground">
            Toàn bộ logo, tiêu đề, phụ đề và sơ đồ chính nằm gọn trong hình chữ nhật an toàn này.
          </p>
        </Card>

        {/* Khối 6: Danh Sách Điều Cấm (Negative Rules) */}
        <Card className="p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 border-b pb-2">
            <div className="rounded bg-destructive/10 p-1 text-destructive">
              <ShieldAlert className="size-4" />
            </div>
            <h4 className="font-bold text-xs uppercase tracking-wider text-destructive">
              Danh Sách Điều Cấm (Negative Rules)
            </h4>
          </div>

          <ul className="text-[11px] text-muted-foreground space-y-1.5 list-disc pl-4">
            <li>CẤM AI sinh chữ hoặc giao diện giả trong video (dễ sai chính tả).</li>
            <li>CẤM tự đổi sang phong cách neon, anime, 3D phô diễn khi chưa duyệt.</li>
            <li>CẤM đổi bảng màu hoặc giọng đọc khác nhau giữa hai video cùng kênh.</li>
            <li>CẤM cắt âm tiết giọng đọc hoặc dùng ước lượng ký tự thay cho đo audio thật.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
