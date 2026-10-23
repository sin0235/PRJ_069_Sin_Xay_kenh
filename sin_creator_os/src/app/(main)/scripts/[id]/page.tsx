"use client";

import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  Save,
  Play,
  RotateCw,
  Plus,
  Trash2,
  GripVertical,
  Sliders,
  CheckCircle2,
  Clock,
  Layers,
  ExternalLink,
  ChevronRight,
  Flame,
  Volume2,
  Film,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

import { mockScriptDetail } from "@/data/mock-creator-data";
import { ScriptBlock, ScriptBlockType, Script } from "@/types";
import { ScriptService } from "@/services/script-service";

export default function ScriptStudioPage() {
  const router = useRouter();
  const params = useParams();
  const scriptId = (params?.id as string) || "script_01";

  const searchParams = useSearchParams();
  const sourceIdeaId = searchParams?.get("source_idea");

  const [script, setScript] = React.useState<Script>(mockScriptDetail);
  const [blocks, setBlocks] = React.useState<ScriptBlock[]>(mockScriptDetail.blocks);
  const [activeCopilotTab, setActiveCopilotTab] = React.useState<"hook" | "tone" | "broll">("hook");
  const [isCopilotThinking, setIsCopilotThinking] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isApproving, setIsApproving] = React.useState(false);
  const [statusMessage, setStatusMessage] = React.useState<{ text: string; isError: boolean } | null>(null);

  // Load script tu Backend API
  React.useEffect(() => {
    let isMounted = true;
    async function loadScript() {
      setIsLoading(true);
      try {
        if (sourceIdeaId && scriptId === "script_01") {
          const existingList = await ScriptService.listScripts({ idea_id: sourceIdeaId });
          if (existingList && existingList.length > 0) {
            if (isMounted) {
              setScript(existingList[0]);
              setBlocks(existingList[0].blocks || mockScriptDetail.blocks);
            }
            return;
          }
          // Neu chua co kich ban cho y tuong nay, tao moi ngay tren backend
          try {
            const created = await ScriptService.createScript({
              idea_id: sourceIdeaId,
              title: "Kich Ban TikTok Sin",
              target_duration_seconds: 30,
            });
            if (isMounted && created) {
              setScript(created);
              setBlocks(created.blocks);
              return;
            }
          } catch {
            // Tiep tuc dung template mock neu backend offline
          }
        }
        const liveScript = await ScriptService.getScriptById(scriptId);
        if (isMounted && liveScript) {
          setScript(liveScript);
          setBlocks(liveScript.blocks || mockScriptDetail.blocks);
        }
      } catch {
        // Fallback mock
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }
    loadScript();
    return () => {
      isMounted = false;
    };
  }, [scriptId, sourceIdeaId]);

  // Calculate total duration
  const totalDuration = blocks.reduce((acc, b) => acc + (b.durationSec || 0), 0);

  const handleSave = async () => {
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const updated = await ScriptService.updateScript({
        ...script,
        blocks,
        targetDurationSec: totalDuration,
      });
      setScript(updated);
      setBlocks(updated.blocks);
      setStatusMessage({ text: "Đã lưu kịch bản vào cơ sở dữ liệu thành công!", isError: false });
    } catch (e: any) {
      setStatusMessage({ text: e?.message || "Lỗi khi lưu kịch bản.", isError: true });
    } finally {
      setIsSaving(false);
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    setStatusMessage(null);
    try {
      const approved = await ScriptService.approveScript(script.id);
      setScript(approved);
      setStatusMessage({ text: "Kịch bản đã được phê duyệt kiểm định thành công!", isError: false });
    } catch (e: any) {
      setStatusMessage({ text: e?.message || "Lỗi khi phê duyệt kịch bản.", isError: true });
    } finally {
      setIsApproving(false);
    }
  };

  const handleBlockChange = (id: string, newContent: string) => {
    setBlocks((prev) =>
      prev.map((b) => (b.id === id ? { ...b, content: newContent } : b))
    );
  };

  const handleAddBlock = () => {
    const newBlock: ScriptBlock = {
      id: `block_${Date.now()}`,
      type: "VALUE",
      title: "Giá Trị Bổ Sung (Value Section)",
      content: "Nhập nội dung chia sẻ hoặc mẹo thực tế tại đây...",
      durationSec: 5,
      visualCue: "Chèn b-roll minh họa cận cảnh thao tác.",
      tone: "energetic",
    };
    setBlocks((prev) => [...prev, newBlock]);
  };

  const handleDeleteBlock = (id: string) => {
    if (blocks.length <= 1) return;
    setBlocks((prev) => prev.filter((b) => b.id !== id));
  };

  const getBlockBadgeColor = (type: ScriptBlockType) => {
    switch (type) {
      case "HOOK":
        return "bg-rose-500/10 text-rose-600 border-rose-500/30";
      case "SETUP":
        return "bg-amber-500/10 text-amber-600 border-amber-500/30";
      case "VALUE":
        return "bg-blue-500/10 text-blue-600 border-blue-500/30";
      case "PROOF":
        return "bg-emerald-500/10 text-emerald-600 border-emerald-500/30";
      case "CTA":
        return "bg-teal-500/10 text-teal-600 border-teal-500/30";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  const triggerAICopilot = (action: string) => {
    setIsCopilotThinking(true);
    setTimeout(() => {
      setIsCopilotThinking(false);
      if (action === "hook_viral") {
        setBlocks((prev) =>
          prev.map((b) =>
            b.type === "HOOK"
              ? {
                  ...b,
                  content:
                    "Đừng tự viết kịch bản TikTok nữa! 99% người xem không nhận ra video này được AI làm từ đầu đến cuối.",
                }
              : b
          )
        );
      }
    }, 700);
  };

  return (
    <div className="space-y-5 pb-20">
      {/* Top Studio Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/80 pb-4">
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
              <h1 className="text-xl font-bold tracking-tight text-foreground line-clamp-1">
                {script.title}
              </h1>
              <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-[10px] font-semibold">
                Khung Chuẩn 5 Tầng TikTok
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Thời lượng ước tính: <span className="font-mono font-bold text-foreground">{totalDuration}s</span> (Chuẩn vàng 24-32s) • Tốc độ đọc: <span className="font-mono text-foreground">{script.estimatedWpm} WPM</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {script.status === "approved" ? (
            <Badge variant="outline" className="border-emerald-500/50 bg-emerald-500/10 text-emerald-600 font-semibold text-xs">
              Đã Duyệt Kiểm Định
            </Badge>
          ) : (
            <Button
              variant="outline"
              size="sm"
              disabled={isApproving}
              onClick={handleApprove}
              className="h-8 text-xs font-medium rounded-lg border-emerald-500/40 text-emerald-600 hover:bg-emerald-500/10 gap-1.5"
            >
              <CheckCircle2 className="size-3.5" />
              <span>{isApproving ? "Đang Duyệt..." : "Phê Duyệt Kịch Bản"}</span>
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/video-studio")}
            className="h-8 text-xs font-medium rounded-lg gap-1.5"
          >
            <Film className="size-3.5" />
            <span>Mở Video Studio</span>
          </Button>

          <Button
            size="sm"
            disabled={isSaving}
            onClick={handleSave}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 shadow-sm"
          >
            <Save className="size-3.5" />
            <span>{isSaving ? "Đang Lưu..." : "Lưu Kịch Bản"}</span>
          </Button>
        </div>
      </div>

      {statusMessage && (
        <div
          className={`p-3 rounded-xl text-xs font-medium border flex items-center justify-between ${
            statusMessage.isError
              ? "bg-rose-500/10 border-rose-500/30 text-rose-600"
              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-600"
          }`}
        >
          <span>{statusMessage.text}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setStatusMessage(null)}
            className="h-6 px-2 text-[11px]"
          >
            Đóng
          </Button>
        </div>
      )}

      {/* 3-Pane Layout: Left Context (3 cols) + Center Block Editor (6 cols) + Right AI Copilot (3 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Pane (3 cols): Context & Strategy */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="rounded-2xl border-border/80 shadow-xs p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Layers className="size-3.5 text-primary" /> Bối Cảnh Chiến Lược
              </span>
              <Badge variant="secondary" className="text-[10px]">
                Context
              </Badge>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block">
                  Ý Tưởng Nền Tảng
                </span>
                <p className="font-semibold text-foreground mt-0.5 leading-snug">
                  {script.context.ideaTitle}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block">
                  Đối Tượng Mục Tiêu
                </span>
                <p className="text-muted-foreground mt-0.5 leading-relaxed">
                  {script.context.targetAudience}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block">
                  Brand Voice (Tone Thương Hiệu)
                </span>
                <p className="text-muted-foreground mt-0.5 leading-relaxed">
                  {script.context.brandVoice}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block">
                  Thông Điệp Cốt Lõi (Key Takeaway)
                </span>
                <p className="text-foreground font-medium mt-0.5 leading-relaxed bg-muted/40 p-2 rounded-lg border border-border/40">
                  {script.context.keyTakeaway}
                </p>
              </div>

              <Separator />

              <div>
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block mb-1.5">
                  Tài Liệu Tham Khảo (References)
                </span>
                <div className="space-y-1.5">
                  {script.context.referenceLinks.map((ref, idx) => (
                    <a
                      key={idx}
                      href={ref.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block p-2 rounded-lg bg-background border border-border/60 hover:border-primary/40 text-xs transition-colors"
                    >
                      <div className="font-semibold text-foreground flex items-center justify-between">
                        <span className="truncate">{ref.title}</span>
                        <ExternalLink className="size-3 text-muted-foreground shrink-0" />
                      </div>
                      <div className="text-[10px] text-muted-foreground truncate">{ref.note}</div>
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Center Pane (6 cols): Structured Block Script Editor */}
        <div className="lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-foreground">
              Phân Đoạn Kịch Bản ({blocks.length} Blocks)
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddBlock}
              className="h-7 text-xs font-medium rounded-lg gap-1"
            >
              <Plus className="size-3" />
              <span>Thêm Block</span>
            </Button>
          </div>

          <div className="space-y-3">
            {blocks.map((block, idx) => (
              <Card
                key={block.id}
                className="rounded-2xl border-border/80 shadow-xs p-4 space-y-3 bg-card hover:border-primary/40 transition-colors"
              >
                {/* Block Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GripVertical className="size-4 text-muted-foreground cursor-grab" />
                    <Badge
                      variant="outline"
                      className={`text-[10px] font-bold px-2 py-0.5 ${getBlockBadgeColor(block.type)}`}
                    >
                      {block.type}
                    </Badge>
                    <span className="text-xs font-bold text-foreground">{block.title}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-muted-foreground bg-muted/60 px-2 py-0.5 rounded">
                      ~{block.durationSec}s
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteBlock(block.id)}
                      className="size-6 text-muted-foreground hover:text-rose-500 rounded"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>

                {/* Spoken Word (Lời Thoại) */}
                <div className="space-y-1">
                  <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block">
                    Lời Thoại / Voiceover (Tiếng Việt):
                  </label>
                  <Textarea
                    value={block.content}
                    onChange={(e) => handleBlockChange(block.id, e.target.value)}
                    rows={3}
                    className="text-xs leading-relaxed resize-none rounded-xl bg-background border-border/80 focus-visible:ring-primary/30"
                  />
                </div>

                {/* Visual Cue & Audio Cue for Editor & Director */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] pt-1">
                  <div className="p-2 rounded-lg bg-muted/40 border border-border/40 space-y-0.5">
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <Film className="size-3 text-primary" /> Gợi Ý Visual / B-Roll:
                    </span>
                    <p className="text-muted-foreground leading-snug">{block.visualCue}</p>
                  </div>

                  <div className="p-2 rounded-lg bg-muted/40 border border-border/40 space-y-0.5">
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <Volume2 className="size-3 text-amber-500" /> Hiệu Ứng Âm Thanh:
                    </span>
                    <p className="text-muted-foreground leading-snug">
                      {block.audioCue || "Âm thanh theo nhịp nhạc nền"}
                    </p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Right Pane (3 cols): AI Copilot Actions */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="rounded-2xl border-border/80 shadow-xs p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Sparkles className="size-3.5 text-primary" /> AI Script Copilot
              </span>
              <Badge variant="outline" className="text-[10px] text-primary border-primary/30 bg-primary/5">
                Assistant
              </Badge>
            </div>

            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-muted-foreground block">
                Tối Ưu Hóa Kịch Bản Một Chạm:
              </span>

              <Button
                variant="outline"
                size="sm"
                onClick={() => triggerAICopilot("hook_viral")}
                disabled={isCopilotThinking}
                className="w-full justify-start text-xs rounded-lg h-8 gap-2 hover:border-primary hover:text-primary"
              >
                <Flame className="size-3.5 text-rose-500" />
                <span>Nâng cấp Hook bùng nổ (Viral)</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => triggerAICopilot("conversational")}
                disabled={isCopilotThinking}
                className="w-full justify-start text-xs rounded-lg h-8 gap-2 hover:border-primary hover:text-primary"
              >
                <Zap className="size-3.5 text-amber-500" />
                <span>Tự nhiên hóa lời thoại (Conversational)</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => triggerAICopilot("storytelling")}
                disabled={isCopilotThinking}
                className="w-full justify-start text-xs rounded-lg h-8 gap-2 hover:border-primary hover:text-primary"
              >
                <Layers className="size-3.5 text-teal-500" />
                <span>Tăng yếu tố kể chuyện (Storytelling)</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => triggerAICopilot("opt_30s")}
                disabled={isCopilotThinking}
                className="w-full justify-start text-xs rounded-lg h-8 gap-2 hover:border-primary hover:text-primary"
              >
                <Clock className="size-3.5 text-blue-500" />
                <span>Cô đọng kịch bản trong 30 giây</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => triggerAICopilot("broll_gen")}
                disabled={isCopilotThinking}
                className="w-full justify-start text-xs rounded-lg h-8 gap-2 hover:border-primary hover:text-primary"
              >
                <Film className="size-3.5 text-emerald-500" />
                <span>Gợi ý danh sách B-roll dựng phim</span>
              </Button>
            </div>

            <Separator />

            {/* Quick Prompt Bar */}
            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-muted-foreground block">
                Yêu Cầu AI Chỉnh Sửa Trực Tiếp:
              </span>
              <Input
                placeholder="Ví dụ: Đổi giọng hài hước, thêm số liệu chứng minh..."
                className="h-8 text-xs rounded-lg"
              />
              <Button
                size="sm"
                className="w-full h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1"
              >
                <Sparkles className="size-3" />
                <span>Áp dụng chỉnh sửa</span>
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
