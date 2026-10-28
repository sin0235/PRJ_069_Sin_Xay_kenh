"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Lightbulb,
  Sparkles,
  LayoutGrid,
  List,
  Plus,
  ShieldCheck,
  TrendingUp,
  FileText,
  Filter,
  Search,
  CheckCircle2,
  Clock,
  ArrowRight,
  Flame,
  MoreVertical,
  Check,
  X,
  HelpCircle,
  AlertTriangle,
  RotateCcw,
  SlidersHorizontal,
  UserCheck,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { IdeaService } from "@/services/idea-service";
import { ContentIdea, IdeaStatus } from "@/types";
import { IdeaReviewModal, ReviewActionType } from "@/components/ideas/idea-review-modal";
import { MetricCoverageBadge } from "@/components/common/metric-coverage-badge";

export default function IdeasPage() {
  const router = useRouter();
  const [viewMode, setViewMode] = React.useState<"board" | "list">("board");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedPillar, setSelectedPillar] = React.useState("all");
  const [statusFilter, setStatusFilter] = React.useState<string>("all");
  const [ideas, setIdeas] = React.useState<ContentIdea[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = React.useState<string | null>(null);

  // State cho IdeaReviewModal
  const [selectedIdeaForReview, setSelectedIdeaForReview] = React.useState<ContentIdea | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = React.useState(false);

  const fetchIdeas = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await IdeaService.getIdeas();
      setIdeas(data);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchIdeas();
  }, [fetchIdeas]);

  const openReviewModal = (idea: ContentIdea) => {
    setSelectedIdeaForReview(idea);
    setIsReviewModalOpen(true);
  };

  const handleReviewSuccess = (updatedCard: any, action: ReviewActionType) => {
    const actionLabel =
      action === "APPROVE"
        ? "Phê duyệt"
        : action === "REJECT"
        ? "Từ chối"
        : action === "REQUEST_EVIDENCE"
        ? "Yêu cầu bổ sung bằng chứng"
        : "Mở lại xem xét";

    setActionSuccess(
      `Đã ${actionLabel.toLowerCase()} thành công ý tưởng "${(selectedIdeaForReview?.title || "").slice(0, 32)}..." (Phiên bản mới: v${(selectedIdeaForReview?.version || 1) + 1})`
    );

    // Cap nhat state cuc bo
    if (selectedIdeaForReview) {
      setIdeas((prev) =>
        prev.map((item) => {
          if (item.id === selectedIdeaForReview.id) {
            let nextStatus: IdeaStatus = "READY_FOR_REVIEW";
            if (action === "APPROVE") nextStatus = "APPROVED";
            else if (action === "REJECT") nextStatus = "REJECTED";
            else if (action === "REQUEST_EVIDENCE") nextStatus = "NEEDS_EVIDENCE";
            else if (action === "REOPEN") nextStatus = "READY_FOR_REVIEW";

            return {
              ...item,
              status: nextStatus,
              version: (item.version || 1) + 1,
              reviewerNotes: updatedCard?.review_reason || item.reviewerNotes,
            };
          }
          return item;
        })
      );
    }
  };

  const filteredIdeas = React.useMemo(() => {
    let list = [...ideas];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.hook.toLowerCase().includes(q) ||
          i.topic.toLowerCase().includes(q)
      );
    }
    if (selectedPillar !== "all") {
      list = list.filter((i) => i.contentPillar === selectedPillar);
    }
    if (statusFilter !== "all") {
      list = list.filter((i) => {
        if (statusFilter === "READY_FOR_REVIEW") {
          return (
            i.status === "READY_FOR_REVIEW" ||
            i.status === "draft" ||
            i.status === "DRAFT"
          );
        }
        if (statusFilter === "APPROVED") {
          return (
            i.status === "APPROVED" ||
            i.status === "validated" ||
            i.status === "ready_to_script"
          );
        }
        if (statusFilter === "NEEDS_EVIDENCE") {
          return i.status === "NEEDS_EVIDENCE";
        }
        if (statusFilter === "REJECTED") {
          return i.status === "REJECTED";
        }
        return i.status === statusFilter;
      });
    }
    return list;
  }, [ideas, searchQuery, selectedPillar, statusFilter]);

  const renderStatusBadge = (status: IdeaStatus, version?: number) => {
    const vStr = version ? ` v${version}` : "";
    switch (status) {
      case "APPROVED":
      case "validated":
      case "ready_to_script":
        return (
          <Badge className="bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 text-[10px] font-semibold gap-1">
            <Check className="size-3" />
            Đã duyệt{vStr}
          </Badge>
        );
      case "READY_FOR_REVIEW":
      case "draft":
      case "DRAFT":
        return (
          <Badge className="bg-amber-500/10 text-amber-600 border border-amber-500/20 text-[10px] font-semibold gap-1">
            <Clock className="size-3" />
            Chờ duyệt{vStr}
          </Badge>
        );
      case "NEEDS_EVIDENCE":
        return (
          <Badge className="bg-orange-500/10 text-orange-600 border border-orange-500/20 text-[10px] font-semibold gap-1">
            <HelpCircle className="size-3" />
            Cần bằng chứng{vStr}
          </Badge>
        );
      case "REJECTED":
        return (
          <Badge className="bg-rose-500/10 text-rose-600 border border-rose-500/20 text-[10px] font-semibold gap-1">
            <X className="size-3" />
            Từ chối{vStr}
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-[10px]">
            {status}
            {vStr}
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Phòng Lab Ý Tưởng (Idea Lab &amp; Workbench)
            </h1>
            <Badge
              variant="outline"
              className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold"
            >
              {ideas.length} Ý Tưởng
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Quy trình kiểm duyệt ý tưởng chuẩn hóa, xác minh bằng chứng và khóa phiên bản lạc quan OCC chống xung đột.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* View Mode Toggle */}
          <div className="flex items-center rounded-lg border border-border/80 p-0.5 bg-muted/40">
            <Button
              variant={viewMode === "board" ? "secondary" : "ghost"}
              size="icon"
              onClick={() => setViewMode("board")}
              className="size-7 rounded-md"
            >
              <LayoutGrid className="size-3.5" />
            </Button>
            <Button
              variant={viewMode === "list" ? "secondary" : "ghost"}
              size="icon"
              onClick={() => setViewMode("list")}
              className="size-7 rounded-md"
            >
              <List className="size-3.5" />
            </Button>
          </div>

          <Button
            size="sm"
            onClick={() => router.push("/ideas/generate")}
            className="h-8 text-xs font-semibold rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5"
          >
            <Sparkles className="size-3.5" />
            <span>Sinh ý tưởng mới</span>
          </Button>
        </div>
      </div>

      {/* Notifications / Alerts */}
      {actionError && (
        <div className="flex items-center gap-2 p-3 text-xs bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-400 rounded-xl">
          <AlertTriangle className="size-4 shrink-0" />
          <span className="flex-1 font-medium">{actionError}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchIdeas}
            className="h-6 px-2 text-[11px] gap-1"
          >
            <RotateCcw className="size-3" /> Làm mới
          </Button>
        </div>
      )}

      {actionSuccess && (
        <div className="flex items-center gap-2 p-3 text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 rounded-xl">
          <CheckCircle2 className="size-4 shrink-0" />
          <span className="flex-1 font-medium">{actionSuccess}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActionSuccess(null)}
            className="h-6 px-2 text-[11px]"
          >
            Đóng
          </Button>
        </div>
      )}

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <Tabs
          value={statusFilter}
          onValueChange={setStatusFilter}
          className="w-full sm:w-auto"
        >
          <TabsList className="bg-muted/50 p-1 rounded-xl h-9">
            <TabsTrigger value="all" className="text-xs rounded-lg px-3">
              Tất cả ({ideas.length})
            </TabsTrigger>
            <TabsTrigger
              value="READY_FOR_REVIEW"
              className="text-xs rounded-lg px-3"
            >
              Chờ duyệt
            </TabsTrigger>
            <TabsTrigger value="APPROVED" className="text-xs rounded-lg px-3">
              Đã duyệt
            </TabsTrigger>
            <TabsTrigger
              value="NEEDS_EVIDENCE"
              className="text-xs rounded-lg px-3"
            >
              Cần bằng chứng
            </TabsTrigger>
            <TabsTrigger value="REJECTED" className="text-xs rounded-lg px-3">
              Từ chối
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-64">
          <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Tìm theo tiêu đề, hook..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 pl-8 text-xs rounded-xl bg-background border-border/70"
          />
        </div>
      </div>

      {/* Card Grid / List Display */}
      {loading ? (
        <div className="text-center py-12 text-xs text-muted-foreground">
          Đang tải danh sách thẻ ý tưởng...
        </div>
      ) : filteredIdeas.length === 0 ? (
        <div className="text-center py-12 text-xs text-muted-foreground bg-muted/20 rounded-2xl border border-dashed border-border/70">
          Không tìm thấy thẻ ý tưởng nào phù hợp với bộ lọc hiện tại.
        </div>
      ) : viewMode === "board" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredIdeas.map((idea) => {
            const isApproved =
              idea.status === "APPROVED" ||
              idea.status === "validated" ||
              idea.status === "ready_to_script";

            return (
              <Card
                key={idea.id}
                className="rounded-2xl border-border/80 shadow-xs flex flex-col justify-between hover:border-border transition-all duration-200 overflow-hidden bg-card"
              >
                <div className="p-4 space-y-3">
                  {/* Top Header: Topic, Status */}
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="secondary" className="text-[10px] font-medium">
                      {idea.topic}
                    </Badge>
                    {renderStatusBadge(idea.status, idea.version)}
                  </div>

                  {/* Title & Hook */}
                  <div className="space-y-1">
                    <h3 className="font-semibold text-sm text-foreground leading-snug line-clamp-2">
                      {idea.title}
                    </h3>
                    <p className="text-[11px] text-muted-foreground italic line-clamp-2 bg-muted/30 p-2 rounded-lg border border-border/40">
                      "{idea.hook}"
                    </p>
                  </div>

                  {/* Metric Coverage Badge & Evidence Verification */}
                  <div className="flex items-center justify-between gap-2 pt-0.5">
                    <MetricCoverageBadge metrics={idea.evidence?.length ? { count: idea.evidence.length } : null} />
                    <span className="text-[10px] text-muted-foreground font-mono">
                      v{idea.version || 1}
                    </span>
                  </div>

                  {/* 3 Dimensional Scores Breakdown */}
                  <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-mono bg-background p-2 rounded-lg border border-border/40">
                    <div>
                      <span className="text-muted-foreground block">Liên quan</span>
                      <span className="font-bold text-foreground">
                        {idea.scores?.relevance == null ? "—" : `${idea.scores.relevance}%`}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">Bắt Trend</span>
                      <span className="font-bold text-foreground">
                        {idea.scores?.trend == null ? "—" : `${idea.scores.trend}%`}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">Điểm AI</span>
                      <span className="font-bold text-primary">
                        {idea.scores?.overall ?? "—"}
                      </span>
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/40">
                    <span className="flex items-center gap-1">
                      <ShieldCheck className="size-3 text-primary" />
                      {idea.evidence?.length || 1} Bằng chứng
                    </span>
                    <span>Tác giả: <strong className="text-foreground">{idea.createdBy || "Chung"}</strong></span>
                  </div>
                </div>

                {/* Card Actions: Review Modal Trigger & Production */}
                <div className="p-3 bg-muted/10 border-t border-border/50 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    {/* Nut Mo Modal Kiem Duyet */}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openReviewModal(idea)}
                      className="h-8 text-xs font-semibold rounded-lg border-[#2B6FB8]/30 text-[#2B6FB8] hover:bg-[#2B6FB8]/10 gap-1.5"
                    >
                      <UserCheck className="size-3.5" />
                      <span>Đánh giá (v{idea.version || 1})</span>
                    </Button>

                    {/* Nut Viet kich ban - Rang buoc chi duoc phep khi da APPROVED */}
                    <Button
                      size="sm"
                      disabled={!isApproved}
                      onClick={() =>
                        router.push(`/scripts/script_01?source_idea=${idea.id}`)
                      }
                      className={`h-8 text-xs font-semibold rounded-lg gap-1 ${
                        isApproved
                          ? "bg-primary hover:bg-primary/90 text-primary-foreground"
                          : "bg-muted text-muted-foreground cursor-not-allowed"
                      }`}
                      title={
                        isApproved
                          ? "Chuyển sang viết kịch bản"
                          : "Cần được phê duyệt (APPROVED) trước khi viết kịch bản"
                      }
                    >
                      <FileText className="size-3" />
                      <span>Viết kịch bản</span>
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        /* List Mode Display */
        <Card className="rounded-2xl border-border/80 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border/70 text-muted-foreground font-semibold">
                  <th className="py-2.5 px-3">Ý Tưởng &amp; Hook</th>
                  <th className="py-2.5 px-3">Trạng Thái</th>
                  <th className="py-2.5 px-3">Dữ Liệu Chỉ Số</th>
                  <th className="py-2.5 px-3 text-center">Điểm AI</th>
                  <th className="py-2.5 px-3 text-right">Thao Tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {filteredIdeas.map((idea) => {
                  const isApproved =
                    idea.status === "APPROVED" ||
                    idea.status === "validated" ||
                    idea.status === "ready_to_script";
                  return (
                    <tr
                      key={idea.id}
                      className="hover:bg-muted/30 transition-colors"
                    >
                      <td className="py-3 px-3 max-w-md">
                        <div className="font-semibold text-foreground text-xs">
                          {idea.title}
                        </div>
                        <div className="text-[11px] text-muted-foreground italic truncate">
                          "{idea.hook}"
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        {renderStatusBadge(idea.status, idea.version)}
                      </td>
                      <td className="py-3 px-3">
                        <MetricCoverageBadge metrics={idea.evidence?.length ? { count: 1 } : null} />
                      </td>
                      <td className="py-3 px-3 text-center font-bold text-primary font-mono text-sm">
                        {idea.scores?.overall ?? "—"}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openReviewModal(idea)}
                            className="h-7 px-2.5 text-[11px] font-semibold border-[#2B6FB8]/30 text-[#2B6FB8] hover:bg-[#2B6FB8]/10 gap-1"
                          >
                            <UserCheck className="size-3" />
                            Đánh giá
                          </Button>
                          <Button
                            size="sm"
                            disabled={!isApproved}
                            onClick={() =>
                              router.push(
                                `/scripts/script_01?source_idea=${idea.id}`
                              )
                            }
                            className={`h-7 text-xs font-semibold rounded-lg gap-1 ${
                              isApproved
                                ? "bg-primary hover:bg-primary/90 text-primary-foreground"
                                : "bg-muted text-muted-foreground cursor-not-allowed"
                            }`}
                            title={
                              isApproved
                                ? "Chuyển sang viết kịch bản"
                                : "Cần được phê duyệt trước khi viết kịch bản"
                            }
                          >
                            <FileText className="size-3" />
                            <span>Viết kịch bản</span>
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Modal Kiem Duyet The Y Tuong Doc Lap */}
      <IdeaReviewModal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        idea={selectedIdeaForReview}
        currentUserId="reviewer_user_admin"
        onReviewSuccess={handleReviewSuccess}
      />
    </div>
  );
}
