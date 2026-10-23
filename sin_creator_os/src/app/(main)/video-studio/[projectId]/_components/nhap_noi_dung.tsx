"use client";

import * as React from "react";
import { Sparkles, Clock, Lock, CheckCircle2, Sliders, AlertCircle, FileText, Share2, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export interface DuLieuNhapNoiDung {
  noiDung: string;
  thoiLuongGiay: number;
  cheDoNoiDung: "GIU_NGUYEN_LOI" | "BIEN_SOAN";
  kenhId: string;
  styleFamilyId: string;
  styleSnapshotHash: string;
  outro: "O1" | "O2" | "O3";
  doiTuong: string;
  mucTieu: string;
}

interface NhapNoiDungProps {
  initialData?: Partial<DuLieuNhapNoiDung>;
  onTiepTuc: (data: DuLieuNhapNoiDung) => void;
  onChonMau: (loaiMau: "60s" | "120s") => void;
}

export function NhapNoiDung({ initialData, onTiepTuc, onChonMau }: NhapNoiDungProps) {
  const [noiDung, setNoiDung] = React.useState(initialData?.noiDung || "");
  const [thoiLuongGiay, setThoiLuongGiay] = React.useState(initialData?.thoiLuongGiay || 120);
  const [cheDoNoiDung, setCheDoNoiDung] = React.useState<"GIU_NGUYEN_LOI" | "BIEN_SOAN">(
    initialData?.cheDoNoiDung || "BIEN_SOAN"
  );
  const [kenhId, setKenhId] = React.useState(initialData?.kenhId || "tiktok_tiktok");
  const [outro, setOutro] = React.useState<"O1" | "O2" | "O3">(initialData?.outro || "O1");
  const [doiTuong, setDoiTuong] = React.useState(initialData?.doiTuong || "Doanh nghiệp & Quản lý");
  const [mucTieu, setMucTieu] = React.useState(
    initialData?.mucTieu || "Giải thích bản chất công nghệ và chuyển đổi nhu cầu giải pháp AI"
  );
  const [loiNhapLieu, setLoiNhapLieu] = React.useState<string | null>(null);

  const styleFamilyId = "baha_giai_thich_cong_nghe_v1";
  const styleSnapshotHash = "sha256:7f8e3d2a1b9c4f5e6a0b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f";

  const handleTiepTuc = (e: React.FormEvent) => {
    e.preventDefault();
    if (!noiDung.trim() || noiDung.trim().length < 20) {
      setLoiNhapLieu("Vui lòng nhập nội dung hoặc tóm tắt chủ đề tối thiểu 20 ký tự.");
      return;
    }
    if (thoiLuongGiay < 30 || thoiLuongGiay > 180) {
      setLoiNhapLieu("Thời lượng thí điểm hỗ trợ từ 30 đến 180 giây.");
      return;
    }
    setLoiNhapLieu(null);
    onTiepTuc({
      noiDung: noiDung.trim(),
      thoiLuongGiay,
      cheDoNoiDung,
      kenhId,
      styleFamilyId,
      styleSnapshotHash,
      outro,
      doiTuong,
      mucTieu,
    });
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Thanh Thông Báo Phong Cách Kênh Đã Khóa */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Lock className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">Quy Chuẩn Phong Cách Kênh:</span>
              <Badge variant="outline" className="border-primary/40 text-primary font-mono text-xs">
                {styleFamilyId}
              </Badge>
              <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs">
                <CheckCircle2 className="mr-1 size-3" />
                ĐÃ KHÓA SNAPSHOT
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 font-mono">
              Hash nhận diện: {styleSnapshotHash.substring(0, 32)}...
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChonMau("60s")}
            className="text-xs"
          >
            Nạp Mẫu 60 Giây (Agent vs Bot)
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChonMau("120s")}
            className="text-xs bg-primary/10 border-primary/30"
          >
            Nạp Mẫu 120 Giây (RAG vs FT)
          </Button>
        </div>
      </div>

      <form onSubmit={handleTiepTuc} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cột Trái & Giữa: Nhập Nội Dung & Thông Số Kịch Bản */}
        <div className="lg:col-span-2 flex flex-col gap-5">
          <Card className="p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <label htmlFor="input-content" className="text-sm font-semibold flex items-center gap-2">
                <FileText className="size-4 text-primary" />
                Nội Dung / Đề Cương / Ý Tưởng Video
              </label>
              <span className="text-xs text-muted-foreground">{noiDung.length} ký tự</span>
            </div>

            <textarea
              id="input-content"
              rows={8}
              value={noiDung}
              onChange={(e) => setNoiDung(e.target.value)}
              placeholder="Nhập nội dung bài viết, ý tưởng kịch bản, hoặc tài liệu công nghệ cần chuyển đổi thành video ngắn TikTok..."
              className="w-full resize-y rounded-lg border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              required
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground">Đối tượng mục tiêu</label>
                <Input
                  value={doiTuong}
                  onChange={(e) => setDoiTuong(e.target.value)}
                  placeholder="Ví dụ: Quản lý doanh nghiệp, Kỹ sư AI"
                  className="text-sm"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground">Mục tiêu truyền thông</label>
                <Input
                  value={mucTieu}
                  onChange={(e) => setMucTieu(e.target.value)}
                  placeholder="Ví dụ: Giải thích dễ hiểu, minh họa ứng dụng"
                  className="text-sm"
                />
              </div>
            </div>
          </Card>

          {loiNhapLieu && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0" />
              <span>{loiNhapLieu}</span>
            </div>
          )}

          <div className="flex justify-end">
            <Button type="submit" size="lg" className="w-full sm:w-auto font-medium">
              <Sparkles className="mr-2 size-4" />
              Tiếp Tục Lập Kịch Bản & Phân Cảnh (Harness + LLM)
            </Button>
          </div>
        </div>

        {/* Cột Phải: Ràng Buộc Kỹ Thuật & Cấu Hình Sản Xuất */}
        <div className="flex flex-col gap-5">
          <Card className="p-5 flex flex-col gap-4">
            <h3 className="text-sm font-semibold flex items-center gap-2 border-b pb-2">
              <Sliders className="size-4 text-primary" />
              Ràng Buộc Kỹ Thuật
            </h3>

            {/* Thời Lượng Mục Tiêu */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium flex items-center gap-1">
                  <Clock className="size-3.5 text-muted-foreground" />
                  Thời lượng mục tiêu:
                </span>
                <span className="font-semibold text-primary font-mono text-sm">
                  {thoiLuongGiay} giây ({thoiLuongGiay * 30} frames)
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2">
                {[60, 90, 120].map((sec) => (
                  <Button
                    key={sec}
                    type="button"
                    variant={thoiLuongGiay === sec ? "default" : "outline"}
                    size="sm"
                    onClick={() => setThoiLuongGiay(sec)}
                    className="text-xs font-mono"
                  >
                    {sec}s {sec === 120 && "(Chuẩn)"}
                  </Button>
                ))}
              </div>
            </div>

            {/* Chế Độ Lời Đọc */}
            <div className="flex flex-col gap-2 pt-2 border-t">
              <span className="text-xs font-medium">Chế độ xử lý lời thoại:</span>
              <div className="grid grid-cols-1 gap-2">
                <label className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                  cheDoNoiDung === "BIEN_SOAN" ? "bg-primary/5 border-primary/40" : "bg-card hover:bg-muted/50"
                }`}>
                  <input
                    type="radio"
                    name="cheDoNoiDung"
                    checked={cheDoNoiDung === "BIEN_SOAN"}
                    onChange={() => setCheDoNoiDung("BIEN_SOAN")}
                    className="mt-0.5"
                  />
                  <div>
                    <span className="font-semibold block">Biên Soạn Có Cấu Trúc (Khuyên dùng)</span>
                    <span className="text-muted-foreground text-[11px]">
                      LLM tối ưu hóa nhịp thoại, phân bổ vừa khít thời lượng và chia phân đoạn trực quan.
                    </span>
                  </div>
                </label>

                <label className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                  cheDoNoiDung === "GIU_NGUYEN_LOI" ? "bg-primary/5 border-primary/40" : "bg-card hover:bg-muted/50"
                }`}>
                  <input
                    type="radio"
                    name="cheDoNoiDung"
                    checked={cheDoNoiDung === "GIU_NGUYEN_LOI"}
                    onChange={() => setCheDoNoiDung("GIU_NGUYEN_LOI")}
                    className="mt-0.5"
                  />
                  <div>
                    <span className="font-semibold block">Giữ Nguyên Lời Đọc</span>
                    <span className="text-muted-foreground text-[11px]">
                      Không thay đổi câu chữ. Dừng chờ nếu thời lượng giọng đọc thực tế lệch chuẩn.
                    </span>
                  </div>
                </label>
              </div>
            </div>

            {/* Mẫu Outro BAHA Group */}
            <div className="flex flex-col gap-2 pt-2 border-t">
              <span className="text-xs font-medium">Mẫu Brand Outro BAHA (5 giây cuối):</span>
              <div className="grid grid-cols-1 gap-1.5">
                {[
                  { id: "O1", label: "O1: Nhận Diện Thuần Túy", desc: "Logo BAHA + Slogan giải pháp AI toàn diện" },
                  { id: "O2", label: "O2: Kêu Gọi Theo Dõi", desc: "Theo dõi kênh để đón nhận kiến thức công nghệ" },
                  { id: "O3", label: "O3: Giải Pháp Doanh Nghiệp", desc: "Khám phá demo hoặc đăng ký tư vấn giải pháp AI" },
                ].map((opt) => (
                  <label
                    key={opt.id}
                    className={`flex items-start gap-2 p-2 rounded border text-xs cursor-pointer ${
                      outro === opt.id ? "bg-primary/5 border-primary/40" : "hover:bg-muted/30"
                    }`}
                  >
                    <input
                      type="radio"
                      name="outro"
                      checked={outro === opt.id}
                      onChange={() => setOutro(opt.id as any)}
                      className="mt-0.5"
                    />
                    <div>
                      <span className="font-semibold block">{opt.label}</span>
                      <span className="text-[11px] text-muted-foreground">{opt.desc}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </form>
    </div>
  );
}
