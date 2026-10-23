"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Sparkles,
  ShieldCheck,
  TrendingUp,
  Eye,
  Heart,
  MessageCircle,
  Share2,
  Clock,
  Layers,
  CheckCircle2,
  ExternalLink,
  Flame,
  Volume2,
  Bookmark,
  RefreshCw,
  Copy,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

import { mockContentAnalysis, mockEvidences } from "@/data/mock-creator-data";
import { EvidenceCard } from "@/components/creator/evidence-card";

export default function ContentAnalysisPage() {
  const router = useRouter();
  const params = useParams();
  const report = mockContentAnalysis;

  const [copiedPattern, setCopiedPattern] = React.useState<string | null>(null);

  const handleCopy = (formula: string, patternName: string) => {
    navigator.clipboard.writeText(formula);
    setCopiedPattern(patternName);
    setTimeout(() => setCopiedPattern(null), 2000);
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Navigation & Header Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="icon"
            onClick={() => router.push("/discover")}
            className="size-8 rounded-lg"
          >
            <ArrowLeft className="size-4" />
          </Button>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground line-clamp-1">
                Bóc Tách & Giải Mã Video (Reverse Engineering)
              </h1>
              <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-[10px] font-semibold">
                Dữ liệu phân tích thực tế
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Phân tích cấu trúc retention 3s vàng, nhịp cắt và công thức tái sử dụng của video triệu view
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => router.push(`/ideas/generate?source=${params.contentId}`)}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>Tạo Ý Tưởng Biến Thể (Inspired Idea)</span>
          </Button>
        </div>
      </div>

      {/* Main Grid Layout: Main Left (Video + Stats + Retention) + Right Insight Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): Video Player Preview + Metrics + Retention Breakdown */}
        <div className="lg:col-span-7 space-y-6">
          {/* Video Preview & Details Card */}
          <Card className="rounded-2xl border-border/80 shadow-xs overflow-hidden">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 p-5">
              {/* 9:16 Video Canvas Player Frame */}
              <div className="md:col-span-5 relative aspect-[9/16] rounded-xl overflow-hidden bg-black/90 border border-border/80 flex items-center justify-center">
                <video
                  src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
                  controls
                  playsInline
                  className="size-full object-cover"
                />
                <span className="absolute top-2 left-2 text-[10px] bg-black/60 text-white px-2 py-0.5 rounded font-mono">
                  9:16 TikTok
                </span>
              </div>

              {/* Video Metadata & Creator Info */}
              <div className="md:col-span-7 flex flex-col justify-between space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <img
                      src={report.creator.avatar}
                      alt={report.creator.username}
                      className="size-8 rounded-full object-cover border border-border"
                    />
                    <div>
                      <div className="text-xs font-bold text-foreground">
                        {report.creator.username}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {(report.creator.followers / 1000).toFixed(0)}K followers • Ngách {report.creator.niche}
                      </div>
                    </div>
                  </div>

                  <h3 className="text-sm font-bold text-foreground leading-snug">
                    {report.title}
                  </h3>

                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Video áp dụng nguyên tắc bẻ gãy thói quen (Pattern Interrupt) ngay ở giây đầu tiên, kết hợp màn hình chia đôi minh họa tương phản.
                  </p>
                </div>

                {/* Performance statistics */}
                <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-muted/40 border border-border/50 text-center font-mono">
                  <div>
                    <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-1">
                      <Eye className="size-3" /> Views
                    </div>
                    <div className="text-xs font-bold text-foreground">
                      {(report.metrics.views / 1000000).toFixed(1)}M
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-1">
                      <TrendingUp className="size-3" /> ER
                    </div>
                    <div className="text-xs font-bold text-primary">
                      {report.metrics.engagementRate}%
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-1">
                      <Clock className="size-3" /> Xem Hết
                    </div>
                    <div className="text-xs font-bold text-emerald-600">
                      {report.metrics.completionRate}%
                    </div>
                  </div>
                </div>

                {/* Hook 3s Breakdown Highlight */}
                <div className="p-3 rounded-xl bg-primary/5 border border-primary/20 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-primary flex items-center gap-1.5">
                      <Flame className="size-3.5" /> Điểm Đánh Giá Hook 3s:
                    </span>
                    <span className="font-bold text-primary font-mono">{report.hookAnalysis.hookScore}/100</span>
                  </div>
                  <div className="text-xs text-foreground font-medium italic">
                    "{report.hookAnalysis.text}"
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Loại: <span className="font-semibold text-foreground">{report.hookAnalysis.type}</span> • Tỉ lệ rớt ở giây 3: <span className="text-emerald-600 font-bold">{report.hookAnalysis.dropoffRateAt3s}%</span> (cực thấp).
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Retention Timeline Breakdown */}
          <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
            <div>
              <CardTitle className="text-sm font-bold">Phân Tách Dòng Thời Gian & Tỷ Lệ Giữ Chân</CardTitle>
              <CardDescription className="text-xs">
                Ước lượng sự tập trung của khán giả qua từng phân đoạn cấu trúc video
              </CardDescription>
            </div>

            <div className="space-y-3">
              {report.structureBreakdown.map((item, idx) => (
                <div key={idx} className="p-3 rounded-xl border border-border/60 bg-muted/20 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                        {item.section}
                      </Badge>
                      <span className="text-muted-foreground font-mono text-[11px]">{item.timestamp}</span>
                    </span>
                    <span className="text-primary font-mono">{item.retentionEstimate}% khán giả còn lại</span>
                  </div>

                  <Progress value={item.retentionEstimate} className="h-1.5" />
                  <p className="text-[11px] text-muted-foreground">{item.description}</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Evidence Provenance Card */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Nguồn Bằng Chứng Xác Thực (Evidence Provenance)
            </h3>
            <EvidenceCard evidence={mockEvidences[0]} />
          </div>
        </div>

        {/* Right Column (5 cols): AI Breakdown, Why It Works, Reusable Patterns */}
        <div className="lg:col-span-5 space-y-6">
          {/* AI Breakdown Card */}
          <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
            <div>
              <CardTitle className="text-sm font-bold flex items-center gap-1.5">
                <Sparkles className="size-4 text-primary" /> Giải Mã Cấu Trúc Bằng AI
              </CardTitle>
              <CardDescription className="text-xs">Bóc tách 10 thông số sản xuất của video</CardDescription>
            </div>

            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <div className="p-2.5 rounded-lg bg-muted/40 border border-border/50">
                <span className="text-[10px] text-muted-foreground block">Định Dạng Video</span>
                <span className="font-semibold text-foreground">{report.aiBreakdown.format}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-muted/40 border border-border/50">
                <span className="text-[10px] text-muted-foreground block">Cấu Trúc Kể Chuyện</span>
                <span className="font-semibold text-foreground">{report.aiBreakdown.storyStructure}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-muted/40 border border-border/50">
                <span className="text-[10px] text-muted-foreground block">Cảm Xúc Kích Hoạt</span>
                <span className="font-semibold text-foreground">{report.aiBreakdown.emotion}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-muted/40 border border-border/50">
                <span className="text-[10px] text-muted-foreground block">Tốc Độ Nói (Speech Pace)</span>
                <span className="font-semibold text-foreground font-mono">{report.aiBreakdown.speechPaceWpm} WPM</span>
              </div>
              <div className="col-span-2 p-2.5 rounded-lg bg-muted/40 border border-border/50">
                <span className="text-[10px] text-muted-foreground block">Phong Cách Dựng (Editing Style)</span>
                <span className="font-semibold text-foreground">{report.aiBreakdown.editingStyle}</span>
              </div>
            </div>
          </Card>

          {/* Why It Works Card */}
          <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-3">
            <div>
              <CardTitle className="text-sm font-bold text-foreground">Tại Sao Video Này Thành Công?</CardTitle>
              <CardDescription className="text-xs">Phân tích dựa trên thuật toán phân phối TikTok</CardDescription>
            </div>

            <div className="space-y-2">
              {report.whyItWorks.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-xs text-muted-foreground leading-relaxed">
                  <CheckCircle2 className="size-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Reusable Patterns Card */}
          <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-3">
            <div>
              <CardTitle className="text-sm font-bold text-foreground flex items-center justify-between">
                <span>Công Thức Có Thể Tái Sử Dụng</span>
                <Badge variant="secondary" className="text-[10px] font-mono">
                  Transformative
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs">
                Không sao chép nguyên mẫu — Biến đổi công thức vào ngách của bạn
              </CardDescription>
            </div>

            <div className="space-y-3">
              {report.reusablePatterns.map((pat, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl border border-border/70 bg-card hover:border-primary/40 transition-colors space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-foreground">{pat.patternName}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCopy(pat.formula, pat.patternName)}
                      className="h-6 text-[10px] px-2 text-primary"
                    >
                      {copiedPattern === pat.patternName ? (
                        "Đã copy!"
                      ) : (
                        <span className="flex items-center gap-1">
                          <Copy className="size-2.5" /> Copy công thức
                        </span>
                      )}
                    </Button>
                  </div>

                  <div className="text-xs font-mono bg-muted/60 p-2 rounded-lg text-primary font-medium">
                    {pat.formula}
                  </div>

                  <div className="text-[11px] text-muted-foreground">
                    <span className="font-semibold text-foreground">Ví dụ áp dụng: </span>
                    {pat.practicalExample}
                  </div>
                </div>
              ))}
            </div>

            <Button
              onClick={() => router.push(`/ideas/generate?source=${report.contentId}`)}
              className="w-full h-9 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 mt-2 shadow-sm"
            >
              <Sparkles className="size-3.5" />
              <span>Tạo Ý Tưởng Mới Dựa Trên Các Công Thức Này</span>
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
