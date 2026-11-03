"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Users,
  TrendingUp,
  Eye,
  Video,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  Search,
  Plus,
  Flame,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function CompetitorsPage() {
  const router = useRouter();
  const [competitors, setCompetitors] = React.useState<any[]>([]);

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Theo Dõi Đối Thủ & Điểm Chuẩn (Competitors)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Opportunity Benchmarking
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Bóc tách điểm mạnh, điểm yếu và khoảng trống cơ hội (gap) của các kênh cùng ngách để tạo ưu thế cạnh tranh.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => router.push("/ideas/generate")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>Khai Thác Khoảng Trống Cơ Hội</span>
          </Button>
        </div>
      </div>

      {/* Competitor Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {competitors.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center p-12 border border-dashed rounded-2xl text-center bg-card/40">
            <Users className="size-10 text-muted-foreground mb-3 opacity-60" />
            <h3 className="text-sm font-semibold text-foreground">Không có dữ liệu đối thủ cạnh tranh</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Chưa có đối thủ nào được thiết lập theo dõi hoặc chưa có dữ liệu đồng bộ từ nền tảng.
            </p>
          </div>
        ) : (
          competitors.map((comp) => (
            <Card key={comp.id} className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4 bg-card">
              {/* Header: Channel info & Growth */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <img
                    src={comp.avatar}
                    alt={comp.channel}
                    className="size-12 rounded-full object-cover border border-border"
                  />
                  <div>
                    <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                      <span>{comp.channel}</span>
                      <Badge variant="secondary" className="text-[10px]">Đang theo dõi</Badge>
                    </h3>
                    <div className="text-[11px] text-muted-foreground">
                      {comp.followers} followers • Tốc độ: {comp.postingRate}
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-xs font-bold font-mono text-emerald-600 block">
                    {comp.growth}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    TB: {comp.avgViews} views
                  </span>
                </div>
              </div>

              {/* Content Pillars */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-semibold text-muted-foreground block">
                  Trụ Cột Nội Dung Cốt Lõi:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {comp.topPillars.map((p: string) => (
                    <Badge key={p} variant="outline" className="text-[10px] bg-muted/30">
                      {p}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Strength vs Weakness Opportunity Analysis */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs pt-1">
                <div className="p-2.5 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-1">
                  <span className="font-semibold text-emerald-600 flex items-center gap-1 text-[11px]">
                    <CheckCircle2 className="size-3" /> Điểm Mạnh Đối Thủ:
                  </span>
                  <p className="text-[11px] text-muted-foreground leading-snug">{comp.strength}</p>
                </div>

                <div className="p-2.5 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-1">
                  <span className="font-semibold text-amber-600 flex items-center gap-1 text-[11px]">
                    <AlertCircle className="size-3" /> Cơ Hội Cho BAHA Group:
                  </span>
                  <p className="text-[11px] text-muted-foreground leading-snug">{comp.weakness}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/50">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push("/discover")}
                  className="h-8 text-xs font-medium rounded-lg"
                >
                  Xem Top Video
                </Button>
                <Button
                  size="sm"
                  onClick={() => router.push(`/ideas/generate?source=${comp.id}`)}
                  className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1"
                >
                  <Sparkles className="size-3" />
                  <span>Sinh Ý Tưởng Vượt Trội</span>
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
