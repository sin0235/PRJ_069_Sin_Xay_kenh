"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Lightbulb,
  Sparkles,
  FileText,
  Upload,
  Video,
  Calendar,
  Layers,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export function GlobalCreateButton() {
  const router = useRouter();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          className="h-8 gap-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-xs px-3 shadow-sm shadow-primary/25 transition-all"
        >
          <Plus className="size-3.5 stroke-[2.5]" />
          <span>Tạo Mới</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56 rounded-xl shadow-xl border-border/80 p-1.5" align="end">
        <DropdownMenuLabel className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider px-2.5 py-1.5">
          Quy Trình Sáng Tạo Nhanh
        </DropdownMenuLabel>

        <DropdownMenuItem
          onClick={() => router.push("/ideas/generate")}
          className="flex items-center gap-2.5 px-2.5 py-2 cursor-pointer rounded-lg hover:bg-primary/10 hover:text-primary transition-colors text-xs font-medium"
        >
          <div className="size-6 rounded-md bg-primary/10 text-primary flex items-center justify-center">
            <Sparkles className="size-3.5" />
          </div>
          <div>
            <div className="font-semibold text-foreground">Sinh Ý Tưởng Bằng AI</div>
            <div className="text-[10px] text-muted-foreground">Sinh ý tưởng từ trends</div>
          </div>
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => router.push("/ideas")}
          className="flex items-center gap-2.5 px-2.5 py-2 cursor-pointer rounded-lg hover:bg-muted transition-colors text-xs font-medium"
        >
          <div className="size-6 rounded-md bg-amber-500/10 text-amber-500 flex items-center justify-center">
            <Lightbulb className="size-3.5" />
          </div>
          <div>
            <div className="font-semibold text-foreground">Tạo Ý Tưởng Mới</div>
            <div className="text-[10px] text-muted-foreground">Nhập idea thủ công</div>
          </div>
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => router.push("/scripts/script_01")}
          className="flex items-center gap-2.5 px-2.5 py-2 cursor-pointer rounded-lg hover:bg-muted transition-colors text-xs font-medium"
        >
          <div className="size-6 rounded-md bg-blue-500/10 text-blue-500 flex items-center justify-center">
            <FileText className="size-3.5" />
          </div>
          <div>
            <div className="font-semibold text-foreground">Soạn Kịch Bản Mới</div>
            <div className="text-[10px] text-muted-foreground">Khung 5 block TikTok</div>
          </div>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onClick={() => router.push("/ai-studio")}
          className="flex items-center gap-2.5 px-2.5 py-2 cursor-pointer rounded-lg hover:bg-muted transition-colors text-xs font-medium"
        >
          <div className="size-6 rounded-md bg-teal-500/10 text-teal-500 flex items-center justify-center">
            <Video className="size-3.5" />
          </div>
          <div>
            <div className="font-semibold text-foreground">Tạo Video Bằng AI</div>
            <div className="text-[10px] text-muted-foreground">TTS, B-roll & render</div>
          </div>
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => router.push("/media")}
          className="flex items-center gap-2.5 px-2.5 py-2 cursor-pointer rounded-lg hover:bg-muted transition-colors text-xs font-medium"
        >
          <div className="size-6 rounded-md bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
            <Upload className="size-3.5" />
          </div>
          <div>
            <div className="font-semibold text-foreground">Tải Lên Video Gốc</div>
            <div className="text-[10px] text-muted-foreground">Lưu vào Thư viện tư liệu</div>
          </div>
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => router.push("/publishing")}
          className="flex items-center gap-2.5 px-2.5 py-2 cursor-pointer rounded-lg hover:bg-muted transition-colors text-xs font-medium"
        >
          <div className="size-6 rounded-md bg-rose-500/10 text-rose-500 flex items-center justify-center">
            <Calendar className="size-3.5" />
          </div>
          <div>
            <div className="font-semibold text-foreground">Lên Lịch Đăng TikTok</div>
            <div className="text-[10px] text-muted-foreground">Hẹn giờ xuất bản đa kênh</div>
          </div>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
