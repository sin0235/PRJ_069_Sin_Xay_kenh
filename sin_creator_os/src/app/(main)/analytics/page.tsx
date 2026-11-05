"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  BarChart3,
  TrendingUp,
  Clock,
  Eye,
  Users,
  Sparkles,
  ArrowRight,
  PieChart,
  Calendar,
  Layers,
  Filter,
  CheckCircle2,
  RefreshCw,
  Lightbulb,
  ShieldCheck,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PublishingService, LearningSignalItem } from "@/services/publishing-service";

const initialRetentionByLength: Array<{ length: string; completionRate: number; views: number }> = [];

const performanceByPillar: Array<{ pillar: string; views: number; er: number; count: number }> = [];

export default function AnalyticsPage() {
  const router = useRouter();
  const [learningSignals, setLearningSignals] = React.useState<LearningSignalItem[]>([]);
  const [isLoadingSignals, setIsLoadingSignals] = React.useState(false);

  const fetchSignals = React.useCallback(async () => {
    setIsLoadingSignals(true);
    try {
      const signals = await PublishingService.listLearningSignals();
      setLearningSignals(signals);
    } catch {
      // Fallback
    } finally {
      setIsLoadingSignals(false);
    }
  }, []);

  React.useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Phân Tích Dữ Liệu Chuyên Sâu (Analytics)
            </h1>
            <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
              Actionable Algorithmic Insights
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Giải mã thuật toán phân phối TikTok, thời lượng tối ưu và mức độ quan tâm của khán giả.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => router.push("/ideas")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>Tạo Content Từ Insight Này</span>
          </Button>
        </div>
      </div>

      {/* Actionable AI Insights Card (Vòng Lặp Insight -> Ý Tưởng Tiếp Theo) */}
      <Card className="rounded-2xl border-primary/30 bg-primary/5 p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-primary/20 text-primary flex items-center justify-center font-bold">
              <Sparkles className="size-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-foreground">
                AI Khám Phá: Video Thời Lượng 22–35 Giây Có Completion Rate Cao Nhất (54.2%)
              </h3>
              <p className="text-xs text-muted-foreground">
                Các video nằm trong khoảng thời gian này có tỷ lệ lưu và bình luận cao hơn 42% so với video dài trên 45 giây.
              </p>
            </div>
          </div>

          <Button
            size="sm"
            onClick={() => router.push("/ideas")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1 shrink-0"
          >
            <span>Tạo Video 28s Ngay</span>
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      </Card>

      {/* Grid: Performance by Length + Performance by Pillar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Retention by Length */}
        <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
          <div>
            <CardTitle className="text-sm font-bold">Tỉ Lệ Xem Hết (Completion Rate) Theo Thời Lượng</CardTitle>
            <CardDescription className="text-xs">
              Mức độ giữ chân người xem theo các khung giây khác nhau
            </CardDescription>
          </div>

          {initialRetentionByLength.length === 0 ? (
            <div className="h-64 w-full flex flex-col items-center justify-center border border-dashed rounded-xl text-center bg-muted/10">
              <BarChart3 className="size-8 text-muted-foreground mb-2 opacity-60" />
              <p className="text-xs font-semibold text-foreground">Không có dữ liệu tỉ lệ xem hết</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Chưa có đủ số liệu video để phân tích theo khung thời lượng.</p>
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={initialRetentionByLength} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" opacity={0.08} />
                  <XAxis dataKey="length" axisLine={false} tickLine={false} tick={{ fontSize: 11 }} />
                  <YAxis axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      borderColor: "var(--border)",
                      borderRadius: "0.75rem",
                      fontSize: "12px",
                    }}
                    formatter={(val: any) => [`${val}%`, "Completion Rate"]}
                  />
                  <Bar dataKey="completionRate" fill="var(--primary)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        {/* Performance by Content Pillar */}
        <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
          <div>
            <CardTitle className="text-sm font-bold">Hiệu Suất Theo Trụ Cột Nội Dung (Content Pillar)</CardTitle>
            <CardDescription className="text-xs">
              So sánh lượt xem và tỷ lệ tương tác giữa các nhóm chủ đề
            </CardDescription>
          </div>

          <div className="space-y-3">
            {performanceByPillar.length === 0 ? (
              <div className="py-12 flex flex-col items-center justify-center border border-dashed rounded-xl text-center bg-muted/10">
                <PieChart className="size-8 text-muted-foreground mb-2 opacity-60" />
                <p className="text-xs font-semibold text-foreground">Không có dữ liệu hiệu suất trụ cột</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Chưa có video được phân nhóm theo trụ cột nội dung.</p>
              </div>
            ) : (
              performanceByPillar.map((p) => (
                <div key={p.pillar} className="p-3 rounded-xl border border-border/60 bg-muted/20 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-foreground">{p.pillar} ({p.count} videos)</span>
                    <span className="text-primary font-mono">{p.views.toLocaleString("vi-VN")} views • {p.er}% ER</span>
                  </div>
                  <Progress value={(p.views / 1000000) * 100} className="h-2" />
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Backend Learning Signals & Experiments (P11 Loop) */}
      <Card className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-border/60 pb-3">
          <div>
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Lightbulb className="size-4 text-primary" /> Tín Hiệu Học Máy & Đề Xuất Tối Ưu (Learning Signals)
            </CardTitle>
            <CardDescription className="text-xs">
              Được tính toán tự động từ vòng phản hồi kênh TikTok sở hữu qua engine P11.
            </CardDescription>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={fetchSignals}
            disabled={isLoadingSignals}
            className="h-8 text-xs rounded-lg gap-1.5"
          >
            <RefreshCw className={`size-3.5 ${isLoadingSignals ? "animate-spin" : ""}`} />
            <span>Cập nhật</span>
          </Button>
        </div>

        {learningSignals.length > 0 ? (
          <div className="space-y-3">
            {learningSignals.map((sig) => (
              <div
                key={sig.id}
                className="p-3.5 rounded-xl border border-border/60 bg-card text-xs space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {sig.signal_type}
                    </Badge>
                    <span className="font-semibold text-foreground">
                      {sig.recommendation_action}
                    </span>
                  </div>
                  <span className="text-muted-foreground font-mono text-[10px]">
                    Độ tin cậy: {(sig.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-muted-foreground text-[11px] leading-relaxed">
                  <span className="font-semibold text-foreground">Công thức:</span> {sig.formula_explanation}
                </p>
                <div className="text-[10px] text-muted-foreground/80 font-mono">
                  Giới hạn: {sig.limitations}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-muted/20 border border-border/50 text-xs text-muted-foreground flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" />
            <span>
              Hệ thống đang tích lũy dữ liệu snapshot phát sóng để kích hoạt mô hình học máy tự động (P11 Feedback Loop).
            </span>
          </div>
        )}
      </Card>
    </div>
  );
}
