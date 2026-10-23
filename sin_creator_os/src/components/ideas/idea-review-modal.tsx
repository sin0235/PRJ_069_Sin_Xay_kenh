"use client";

import * as React from "react";
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  RotateCcw,
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  Clock,
  Loader2,
  UserCheck,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ContentIdea, IdeaStatus } from "@/types";
import { IdeaService } from "@/services/idea-service";

export type ReviewActionType = "APPROVE" | "REJECT" | "REQUEST_EVIDENCE" | "REOPEN";

export interface IdeaReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  idea: ContentIdea | null;
  currentUserId?: string;
  onReviewSuccess: (updatedCard: any, action: ReviewActionType) => void;
}

/**
 * IdeaReviewModal: Hop thoai kiem duyet the y tuong chuyen sau
 * Tuan thu cac ranh gioi:
 * 1. Khoa lac quan OCC: expected_version, expected_status
 * 2. Rao chan Bon Mat (Four-Eyes Principle / No Self-Approval)
 * 3. 4 Thao tac nghiem ngat: APPROVE, REJECT, REQUEST_EVIDENCE, REOPEN
 * 4. Rule 9: 100% SVG Vector (Lucide), 0 Emoji
 */
export function IdeaReviewModal({
  isOpen,
  onClose,
  idea,
  currentUserId = "current-reviewer-user",
  onReviewSuccess,
}: IdeaReviewModalProps) {
  const [reviewReason, setReviewReason] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [isConflict, setIsConflict] = React.useState(false);

  // Reset form khi modal mo len voi y tuong moi
  React.useEffect(() => {
    if (isOpen) {
      setReviewReason("");
      setErrorMessage(null);
      setIsConflict(false);
    }
  }, [isOpen, idea?.id]);

  if (!idea) return null;

  const currentVersion = idea.version || 1;
  const currentStatus = idea.status || "READY_FOR_REVIEW";
  const isCreator = Boolean(idea.createdBy && (idea.createdBy === currentUserId || idea.createdBy === "creator_user_id"));

  // Validate ly do danh gia toi thieu 3 ky tu
  const isReasonValid = reviewReason.trim().length >= 3;

  const handleAction = async (action: ReviewActionType) => {
    if (!isReasonValid) {
      setErrorMessage("Lý do đánh giá bắt buộc phải có ít nhất 3 ký tự.");
      return;
    }

    // Kiem tra ranh gioi Bon Mat o client truoc khi goi API
    if (action === "APPROVE" && isCreator) {
      setErrorMessage(
        "Quy tắc Bốn Mắt: Người tạo ý tưởng không được phép tự phê duyệt (APPROVE) tác phẩm của chính mình."
      );
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setIsConflict(false);

    try {
      const res = await IdeaService.reviewIdea(
        idea.id,
        action,
        currentStatus,
        currentVersion,
        reviewReason.trim()
      );

      if (res.success) {
        onReviewSuccess(res.updatedCard, action);
        onClose();
      } else {
        if (res.error?.includes("409") || res.error?.includes("Stale") || res.error?.includes("STALE_VERSION")) {
          setIsConflict(true);
          setErrorMessage(
            "Thẻ ý tưởng đã được chỉnh sửa bởi người khác, vui lòng tải lại trang để xem phiên bản mới nhất."
          );
        } else if (res.error?.includes("SELF_APPROVAL") || res.error?.includes("Bốn Mắt") || res.error?.includes("403")) {
          setErrorMessage(
            "Người tạo không được phép tự phê duyệt ý tưởng của chính mình (Quy tắc Bốn Mắt)."
          );
        } else {
          setErrorMessage(res.error || "Không thể hoàn tất thao tác đánh giá.");
        }
      }
    } catch (e: any) {
      setErrorMessage(e?.message || "Lỗi mạng khi kết nối máy chủ.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="space-y-2">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-lg font-bold text-foreground flex items-center gap-2">
              <UserCheck className="size-5 text-[#2B6FB8]" />
              <span>Kiểm Duyệt Thẻ Ý Tưởng</span>
            </DialogTitle>
            <div className="flex items-center gap-1.5">
              <Badge variant="outline" className="text-[11px] font-semibold border-primary/30 text-primary">
                v{currentVersion}
              </Badge>
              <Badge variant="secondary" className="text-[11px] font-medium">
                {currentStatus}
              </Badge>
            </div>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Thao tác cập nhật trạng thái sẽ được lưu trữ với khóa lạc quan OCC và kiểm toán danh tính người duyệt.
          </DialogDescription>
        </DialogHeader>

        {/* Thong tin the y tuong */}
        <div className="p-3.5 rounded-xl border border-border/80 bg-muted/30 space-y-2">
          <div className="text-xs font-semibold text-foreground line-clamp-2">
            {idea.title}
          </div>
          {idea.hook && (
            <div className="text-[11px] text-muted-foreground bg-background/80 p-2.5 rounded-lg border border-border/50">
              <span className="font-semibold text-primary block mb-0.5">Hook mở đầu:</span>
              <span className="italic line-clamp-2">"{idea.hook}"</span>
            </div>
          )}
          <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
            <span>Tác giả: <strong className="text-foreground">{idea.createdBy || "Chưa xác định"}</strong></span>
            <span>Chủ đề: <strong className="text-foreground">{idea.topic || "Chung"}</strong></span>
          </div>
        </div>

        {/* Canh bao quy tac Bon Mat (Four-Eyes Principle) */}
        {isCreator && (
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-400 text-xs flex items-start gap-2.5">
            <ShieldAlert className="size-4 shrink-0 mt-0.5 text-amber-600" />
            <div>
              <span className="font-semibold block">Rào chắn Bốn Mắt (Separation of Duties):</span>
              <span>Bạn là người tạo ý tưởng này. Nút <strong>Phê Duyệt (Approve)</strong> sẽ bị khóa để ngăn chặn hành vi tự duyệt tác phẩm của chính mình.</span>
            </div>
          </div>
        )}

        {/* O nhap ly do danh gia bat buoc */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <label htmlFor="review-reason" className="font-semibold text-foreground flex items-center gap-1">
              <span>Lý do đánh giá &amp; Ghi chú kiểm toán</span>
              <span className="text-rose-500">*</span>
            </label>
            <span className={`text-[10px] ${reviewReason.trim().length >= 3 ? "text-emerald-600 font-medium" : "text-muted-foreground"}`}>
              {reviewReason.trim().length}/3 ký tự tối thiểu
            </span>
          </div>
          <Textarea
            id="review-reason"
            value={reviewReason}
            onChange={(e) => setReviewReason(e.target.value)}
            placeholder="Nhập nhận xét chi tiết, căn cứ bằng chứng hoặc yêu cầu chỉnh sửa..."
            className="text-xs min-h-[85px] resize-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Thong bao loi / Xung dot phien ban */}
        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-400 text-xs flex items-start gap-2">
            <AlertTriangle className="size-4 shrink-0 mt-0.5" />
            <div className="flex-1 font-medium">{errorMessage}</div>
            {isConflict && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.location.reload()}
                className="h-6 px-2 text-[10px] border-rose-300 hover:bg-rose-100"
              >
                Tải lại trang
              </Button>
            )}
          </div>
        )}

        {/* 4 Nut thao tac danh gia */}
        <DialogFooter className="flex-col sm:flex-row gap-2 pt-2 border-t border-border/80">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-xs"
          >
            Hủy bỏ
          </Button>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-end">
            {/* 1. Nut Mo lai xem xet (REOPEN) */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isSubmitting || !isReasonValid}
              onClick={() => handleAction("REOPEN")}
              className="text-xs border-[#2B6FB8]/40 text-[#2B6FB8] hover:bg-[#2B6FB8]/10 gap-1.5"
            >
              <RotateCcw className="size-3.5" />
              <span>Mở Lại</span>
            </Button>

            {/* 2. Nut Yeu cau bo sung bang chung (REQUEST_EVIDENCE) */}
            <Button
              type="button"
              size="sm"
              disabled={isSubmitting || !isReasonValid}
              onClick={() => handleAction("REQUEST_EVIDENCE")}
              className="text-xs bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
            >
              <HelpCircle className="size-3.5" />
              <span>Cần Chứng Cứ</span>
            </Button>

            {/* 3. Nut Tu choi (REJECT) */}
            <Button
              type="button"
              size="sm"
              disabled={isSubmitting || !isReasonValid}
              onClick={() => handleAction("REJECT")}
              className="text-xs bg-rose-600 hover:bg-rose-700 text-white gap-1.5"
            >
              <XCircle className="size-3.5" />
              <span>Từ Chối</span>
            </Button>

            {/* 4. Nut Phe duyet (APPROVE) - Mau xanh Baha Group #246849 */}
            <Button
              type="button"
              size="sm"
              disabled={isSubmitting || !isReasonValid || isCreator}
              onClick={() => handleAction("APPROVE")}
              className="text-xs bg-[#246849] hover:bg-[#1d533a] text-white font-semibold gap-1.5"
            >
              {isSubmitting ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="size-3.5" />
              )}
              <span>Phê Duyệt</span>
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
