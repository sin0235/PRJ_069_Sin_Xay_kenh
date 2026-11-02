"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Flame,
  TrendingUp,
  Sparkles,
  Music,
  Hash,
  Type,
  Video,
  Layers,
  Search,
  ExternalLink,
  ShieldCheck,
  ChevronRight,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";

export default function TrendsPage() {
  const router = useRouter();
  const [selectedType, setSelectedType] = React.useState("all");
  const [trends, setTrends] = React.useState<any[]>([]);

  const getStageBadge = (stage: string) => {
    switch (stage) {
      case "Emerging":
        return "border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10";
      case "Growing":
        return "border-teal-500/40 text-teal-600 dark:text-teal-400 bg-teal-500/10";
      case "Peak":
        return "border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/10";
      case "Cooling":
        return "border-slate-500/40 text-slate-500 bg-slate-500/10";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

export default function EmptyDataPage() {
  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Radar Bắt Xu Hướng (TikTok Trends Radar)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Live Algorithmic Momentum
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Quét và phát hiện sớm các âm thanh, hashtag, định dạng video và từ khóa đang bùng nổ trước khi bão hòa.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => router.push("/ideas/generate")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>Tạo Content Theo Trend Hot Nhất</span>
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {["all", "Topic", "Sound", "Format", "Hashtag"].map((t) => (
          <Button
            key={t}
            variant={selectedType === t ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedType(t)}
            className="h-8 text-xs rounded-xl"
          >
            {t === "all" ? "Tất Cả Loại Xu Hướng" : t}
          </Button>
        ))}
      </div>

      {/* Trends Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {trends.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center p-12 border border-dashed rounded-2xl text-center bg-card/40">
            <TrendingUp className="size-10 text-muted-foreground mb-3 opacity-60" />
            <h3 className="text-sm font-semibold text-foreground">Không có dữ liệu xu hướng</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Hiện tại chưa thu thập được dữ liệu xu hướng mới từ thuật toán TikTok. Vui lòng thử lại sau.
            </p>
          </div>
        ) : (
          trends.map((trend) => (
            <Card
              key={trend.id}
              className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4 hover:border-primary/40 transition-all bg-card"
            >
              {/* Header: Trend Name, Type, Stage */}
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className={`text-[10px] font-bold ${getStageBadge(trend.stage)}`}>
                      Giai đoạn: {trend.stage}
                    </Badge>
                    <Badge variant="secondary" className="text-[10px] font-mono">
                      {trend.type}
                    </Badge>
                  </div>
                  <h3 className="text-sm font-bold text-foreground">{trend.name}</h3>
                </div>

                <div className="text-right">
                  <div className="text-xs font-bold font-mono text-primary flex items-center justify-end gap-1">
                    <Flame className="size-3 text-rose-500 fill-current" />
                    <span>Momentum: {trend.momentum}/100</span>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-600 block">
                    {trend.growthCurve}
                  </span>
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-muted-foreground leading-relaxed">
                {trend.description}
              </p>

              {/* Metadata & Signals */}
              <div className="grid grid-cols-2 gap-2 text-[11px] p-2.5 rounded-xl bg-muted/40 border border-border/50">
                <div>
                  <span className="text-muted-foreground block text-[10px]">Quy mô lượt xem:</span>
                  <span className="font-bold text-foreground font-mono">{trend.volume}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px]">Độ phù hợp tệp người xem:</span>
                  <span className="font-bold text-primary">{trend.audienceMatch}</span>
                </div>
              </div>

              {/* Action */}
              <div className="flex items-center justify-between pt-2 border-t border-border/50">
                <span className="text-[11px] text-muted-foreground flex items-center gap-1 font-mono">
                  <Zap className="size-3 text-amber-500" /> Tín hiệu tươi mới: {trend.freshness}
                </span>

                <Button
                  size="sm"
                  onClick={() => router.push(`/ideas/generate?trend=${trend.id}`)}
                  className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1"
                >
                  <Sparkles className="size-3" />
                  <span>Bắt Trend Này</span>
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
