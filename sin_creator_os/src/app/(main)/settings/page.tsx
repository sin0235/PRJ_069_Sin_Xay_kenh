"use client";

import * as React from "react";
import { Settings, Save, Sparkles, Shield, User, Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

export default function SettingsPage() {
  return (
    <div className="space-y-6 pb-20 max-w-3xl">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Cài Đặt Không Gian Làm Việc (Settings)
          </h1>
          <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
            BAHA Creator Studio
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          Tùy chỉnh thông số mặc định, ngôn ngữ kịch bản và chuẩn video xuất xưởng.
        </p>
      </div>

      <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
        <CardTitle className="text-sm font-bold text-foreground">Cấu Hình Xuất Video Mặc Định</CardTitle>

        <div className="space-y-3 text-xs">
          <div>
            <label className="text-[11px] font-semibold text-muted-foreground block mb-1">
              Tỉ lệ khung hình mặc định
            </label>
            <Input defaultValue="9:16 (1080 x 1920 px) - TikTok Standard" disabled className="h-8 text-xs bg-muted/40 font-mono" />
          </div>

          <div>
            <label className="text-[11px] font-semibold text-muted-foreground block mb-1">
              Chuẩn âm lượng (Audio Loudness Target)
            </label>
            <Input defaultValue="-14 LUFS (±1 LUFS)" disabled className="h-8 text-xs bg-muted/40 font-mono" />
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl border border-border/60 bg-muted/20">
            <div>
              <div className="font-semibold text-foreground">Bật Safe Zone TikTok tự động</div>
              <div className="text-[10px] text-muted-foreground">Cảnh báo khi phụ đề hoặc logo rơi vào vùng bị nút tương tác che</div>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl border border-border/60 bg-muted/20">
            <div>
              <div className="font-semibold text-foreground">Tự động sinh giọng đọc AI (Auto-TTS)</div>
              <div className="text-[10px] text-muted-foreground">Chuyển kịch bản thành voiceover ngay khi duyệt xong 5 block</div>
            </div>
            <Switch defaultChecked />
          </div>
        </div>

        <div className="pt-2 border-t border-border/50 flex justify-end">
          <Button size="sm" className="h-8 text-xs font-semibold rounded-lg bg-primary text-primary-foreground gap-1.5 shadow-sm">
            <Save className="size-3.5" />
            <span>Lưu Thiết Lập</span>
          </Button>
        </div>
      </Card>
    </div>
  );
}
