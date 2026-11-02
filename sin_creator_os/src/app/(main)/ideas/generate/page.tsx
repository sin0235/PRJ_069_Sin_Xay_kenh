"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ArrowLeft,
  ShieldCheck,
  RotateCw,
  Plus,
  FileText,
  Sliders,
  CheckCircle2,
  Bookmark,
  ExternalLink,
  Flame,
  Zap,
  Layers,
  ChevronRight,
  TrendingUp,
  Lightbulb,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";

import { IdeaService } from "@/services/idea-service";
import { EvidenceCard } from "@/components/creator/evidence-card";
import { ContentIdea, EvidenceSource } from "@/types";

export default function IdeaGeneratorPage() {
  const router = useRouter();

  // Generator Config State
  const [niche, setNiche] = React.useState("");
  const [audience, setAudience] = React.useState("");
  const [objective, setObjective] = React.useState("");
  const [pillar, setPillar] = React.useState("");
  const [tone, setTone] = React.useState("");
  const [videoLength, setVideoLength] = React.useState("");
  const [quantity, setQuantity] = React.useState("3");

  const [sources, setSources] = React.useState({
    tiktokTrends: true,
    competitors: true,
    savedResearch: true,
    channelHistory: true,
    manualRef: false,
  });

  const [isGenerating, setIsGenerating] = React.useState(false);
  const [generatedList, setGeneratedList] = React.useState<ContentIdea[]>([]);
  const [evidences, setEvidences] = React.useState<EvidenceSource[]>([]);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [generationSource, setGenerationSource] = React.useState<string | null>(null);

  // Nạp danh sách ý tưởng ban đầu từ Backend
  React.useEffect(() => {
    IdeaService.getIdeas("all").then((data) => {
      if (data && data.length > 0) {
        setGeneratedList(data);
      }
    }).catch(() => {
      // Giữ danh sách rỗng, không tự tạo mock
    });
  }, []);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setErrorMessage(null);
    try {
      const res = await IdeaService.generateIdeas({
        niche,
        targetAudience: audience,
        contentPillar: pillar,
        targetLengthSec: 28,
        desiredQuantity: parseInt(quantity, 10) || 3,
      });
      if (res.success && res.ideas && res.ideas.length > 0) {
        setGeneratedList(res.ideas);
        setGenerationSource(res.generationSource || 'llm_router');
      } else if (res.error) {
        setErrorMessage(res.error);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "Lỗi mạng khi kết nối backend API.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="icon"
            onClick={() => router.push("/ideas")}
            className="size-8 rounded-lg"
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground">
                AI Idea Generator (Sinh Ý Tưởng Bằng Bằng Chứng)
              </h1>
              <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-[10px] font-semibold">
                Multi-Source Synthesizer
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Kết hợp tín hiệu xu hướng TikTok, đối thủ và dữ liệu lịch sử kênh để tạo ý tưởng đột phá
            </p>
          </div>
        </div>

        <Button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="h-9 px-4 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold gap-1.5 shadow-sm"
        >
          {isGenerating ? (
            <RotateCw className="size-3.5 animate-spin" />
          ) : (
            <Sparkles className="size-3.5" />
          )}
          <span>{isGenerating ? "Đang tổng hợp dữ liệu..." : "Sinh Ý Tưởng Mới"}</span>
        </Button>
      </div>

      {/* 3-Pane Layout: Left Config (3 cols) + Center Generated (6 cols) + Right Evidence (3 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Pane (3 cols): Generation Configuration */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="rounded-2xl border-border/80 shadow-xs p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Sliders className="size-3.5 text-primary" /> Cấu Hình Đầu Vào
              </span>
              <Badge variant="secondary" className="text-[10px]">
                Config
              </Badge>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Ngách Nội Dung (Niche)
                </label>
                <Input
                  value={niche}
                  onChange={(e) => setNiche(e.target.value)}
                  className="h-8 text-xs rounded-lg"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Đối Tượng Khán Giả Mục Tiêu
                </label>
                <Input
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  className="h-8 text-xs rounded-lg"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Trụ Cột Nội Dung (Content Pillar)
                </label>
                <Select value={pillar} onValueChange={setPillar}>
                  <SelectTrigger className="h-8 text-xs rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="rounded-xl">
                    <SelectItem value="AI Workflow & Automation">AI Workflow & Automation</SelectItem>
                    <SelectItem value="Deconstruction / Case Study">Deconstruction / Case Study</SelectItem>
                    <SelectItem value="Technical Tips">Technical Tips & Guidelines</SelectItem>
                    <SelectItem value="Tool Roundup / Listicle">Tool Roundup / Listicle</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Tone Giọng & Phong Cách
                </label>
                <Input
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="h-8 text-xs rounded-lg"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Thời Lượng Video Dự Kiến
                </label>
                <Select value={videoLength} onValueChange={setVideoLength}>
                  <SelectTrigger className="h-8 text-xs rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="rounded-xl">
                    <SelectItem value="15-20 giây">15 - 20 giây (Siêu ngắn)</SelectItem>
                    <SelectItem value="24-32 giây (Optimal)">24 - 32 giây (Tối ưu nhất)</SelectItem>
                    <SelectItem value="45-60 giây">45 - 60 giây (Chuyên sâu)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Separator />

              {/* Data Sources Checkboxes */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-foreground block">
                  Nguồn Dữ Liệu Tham Chiếu:
                </label>

                <div className="space-y-1.5 text-xs">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={sources.tiktokTrends}
                      onCheckedChange={(c) => setSources({ ...sources, tiktokTrends: !!c })}
                    />
                    <span className="text-muted-foreground text-[11px]">TikTok Trending Radar</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={sources.competitors}
                      onCheckedChange={(c) => setSources({ ...sources, competitors: !!c })}
                    />
                    <span className="text-muted-foreground text-[11px]">Video kênh đối thủ trực tiếp</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={sources.savedResearch}
                      onCheckedChange={(c) => setSources({ ...sources, savedResearch: !!c })}
                    />
                    <span className="text-muted-foreground text-[11px]">Thư viện nghiên cứu đã lưu</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={sources.channelHistory}
                      onCheckedChange={(c) => setSources({ ...sources, channelHistory: !!c })}
                    />
                    <span className="text-muted-foreground text-[11px]">Dữ liệu lịch sử kênh BAHA Group</span>
                  </label>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Center Pane (6 cols): Generated Ideas Cards */}
        <div className="lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-foreground">
              Ý Tưởng Đã Tạo ({generatedList.length})
            </span>
            <span className="text-muted-foreground">Đã kiểm chứng với thuật toán TikTok</span>
          </div>

          <div className="space-y-4">
            {generatedList.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-12 border border-dashed rounded-2xl text-center bg-card/40">
                <Lightbulb className="size-10 text-muted-foreground mb-3 opacity-60" />
                <h3 className="text-sm font-semibold text-foreground">Không có dữ liệu ý tưởng</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                  Chưa có ý tưởng nào được tạo hoặc lưu trong hệ thống. Hãy bấm nút "Khởi Chạy Sinh Ý Tưởng" ở cột bên trái để bắt đầu.
                </p>
              </div>
            ) : (
              generatedList.map((idea) => (
              <Card
                key={idea.id}
                className="rounded-2xl border-border/80 shadow-xs p-5 space-y-4 hover:border-primary/50 transition-all bg-card"
              >
                {/* Header Info */}
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Badge variant="outline" className="text-[10px] text-primary border-primary/30 bg-primary/5 font-semibold">
                        {idea.topic}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px] font-mono text-emerald-600">
                        {idea.freshness || "—"}
                      </Badge>
                      <span className="text-[11px] text-muted-foreground font-mono">
                        Dựng: {idea.estimatedProductionEffort || "—"}
                      </span>
                    </div>

                    <h3 className="text-sm font-bold text-foreground leading-snug">
                      {idea.title}
                    </h3>
                  </div>

                  <div className="flex flex-col items-end shrink-0">
                    <div className="px-2 py-0.5 rounded-full bg-primary/10 text-primary font-bold text-xs font-mono">
                      {idea.scores?.overall == null ? "—" : `${idea.scores.overall}/100`}
                    </div>
                    <span className="text-[9px] text-muted-foreground">Điểm khả thi</span>
                  </div>
                </div>

                {/* One line concept & Hook */}
                <div className="space-y-2 text-xs">
                  <div className="text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-foreground">Ý tưởng cốt lõi: </span>
                    {idea.oneLineConcept}
                  </div>

                  {/* Hook Box */}
                  <div className="p-3 rounded-xl bg-primary/5 border border-primary/20 space-y-1">
                    <div className="flex items-center justify-between text-[10px] font-semibold text-primary uppercase tracking-wider">
                      <span>Móc Câu 3 Giây Vàng (Hook)</span>
                      <span className="text-emerald-600 font-mono">Dự kiến &gt; 50% xem hết</span>
                    </div>
                    <div className="text-xs font-medium text-foreground italic leading-relaxed">
                      "{idea.hook}"
                    </div>
                  </div>
                </div>

                {/* 5-Block Video Structure Preview */}
                <div className="p-3 rounded-xl bg-muted/40 border border-border/60 text-xs space-y-2">
                  <span className="text-[10px] font-bold text-foreground uppercase tracking-wider block">
                    Cấu Trúc Khung Video 5 Tầng:
                  </span>
                  <div className="grid grid-cols-5 gap-1.5 text-center text-[10px]">
                    <div className="p-1 rounded bg-background border border-border/40 font-mono">
                      <span className="text-primary font-bold block">0-3s</span>
                      <span className="text-muted-foreground truncate block">HOOK</span>
                    </div>
                    <div className="p-1 rounded bg-background border border-border/40 font-mono">
                      <span className="text-primary font-bold block">4-8s</span>
                      <span className="text-muted-foreground truncate block">SETUP</span>
                    </div>
                    <div className="p-1 rounded bg-background border border-border/40 font-mono">
                      <span className="text-primary font-bold block">9-20s</span>
                      <span className="text-muted-foreground truncate block">VALUE</span>
                    </div>
                    <div className="p-1 rounded bg-background border border-border/40 font-mono">
                      <span className="text-primary font-bold block">21-27s</span>
                      <span className="text-muted-foreground truncate block">PROOF</span>
                    </div>
                    <div className="p-1 rounded bg-background border border-border/40 font-mono">
                      <span className="text-primary font-bold block">28-32s</span>
                      <span className="text-muted-foreground truncate block">CTA</span>
                    </div>
                  </div>
                </div>

                {/* Why this idea */}
                <div className="text-[11px] text-muted-foreground bg-accent/20 p-2.5 rounded-lg border border-accent/30 leading-relaxed">
                  <span className="font-semibold text-foreground">Tại sao nên làm ý tưởng này: </span>
                  {idea.whyThisIdea}
                </div>

                {/* Actions */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/50 text-xs">
                  <div className="flex items-center gap-1.5">
                    <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground">
                      <Bookmark className="size-3 mr-1" /> Lưu
                    </Button>
                    <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground">
                      <RotateCw className="size-3 mr-1" /> Sinh biến thể
                    </Button>
                  </div>

                  <Button
                    size="sm"
                    onClick={() => router.push("/scripts/script_01")}
                    className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
                  >
                    <FileText className="size-3.5" />
                    <span>Tạo Kịch Bản Ngay</span>
                  </Button>
                </div>
              </Card>
            )))}
          </div>
        </div>

        {/* Right Pane (3 cols): Evidence & Context */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="rounded-2xl border-border/80 shadow-xs p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <ShieldCheck className="size-3.5 text-primary" /> Bằng Chứng Dữ Liệu
              </span>
              <Badge variant="outline" className="text-[10px]">
                Nguồn dữ liệu
              </Badge>
            </div>

            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Các video và tín hiệu thực tế được nạp vào AI để tạo ra các ý tưởng trên:
            </p>

            <div className="space-y-3 pt-1">
              {evidences.length === 0 ? (
                <div className="py-6 text-center text-xs text-muted-foreground border border-dashed rounded-xl">
                  Không có dữ liệu bằng chứng trích dẫn
                </div>
              ) : (
                evidences.map((ev) => (
                  <EvidenceCard key={ev.id} evidence={ev} compact />
                ))
              )}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push("/discover")}
              className="w-full text-xs font-medium rounded-lg h-8 mt-2"
            >
              Tìm Thêm Nguồn Khác Trong Discover
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
