"use client";

import * as React from "react";
import { ExternalLink, ShieldCheck, TrendingUp, Eye, Heart, MessageCircle, Share2, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EvidenceSource } from "@/types";

interface EvidenceCardProps {
  evidence: EvidenceSource;
  compact?: boolean;
}

export function EvidenceCard({ evidence, compact = false }: EvidenceCardProps) {
  const formatNum = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  if (compact) {
    return (
      <div className="flex items-center justify-between p-2 rounded-lg bg-muted/50 border border-border/60 text-xs">
        <div className="flex items-center gap-2 truncate">
          <ShieldCheck className="size-3.5 text-primary shrink-0" />
          <span className="font-semibold text-foreground truncate">{evidence.author}</span>
          <span className="text-[11px] text-muted-foreground truncate">({evidence.sourceName})</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant="secondary" className="text-[10px] font-mono">
            {formatNum(evidence.metricsSnapshot.views)} views
          </Badge>
          <a
            href={evidence.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-primary transition-colors"
          >
            <ExternalLink className="size-3" />
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/80 bg-card p-3.5 space-y-3 shadow-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="size-7 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
            {evidence.author.slice(1, 3).toUpperCase()}
          </div>
          <div>
            <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <span>{evidence.author}</span>
              <Badge variant="outline" className="text-[9px] px-1.5 py-0 border-primary/30 text-primary bg-primary/5">
                {evidence.sourceType.replace("_", " ")}
              </Badge>
            </div>
            <div className="text-[10px] text-muted-foreground">
              Nguồn: {evidence.sourceName} • Thu thập: {new Date(evidence.collectedAt).toLocaleDateString("vi-VN")}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
          <ShieldCheck className="size-3" />
          <span>{evidence.confidence}% Tin cậy</span>
        </div>
      </div>

      {/* Snapshot metrics */}
      <div className="grid grid-cols-4 gap-1.5 py-2 px-2.5 rounded-lg bg-muted/40 border border-border/40 text-center font-mono">
        <div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-0.5">
            <Eye className="size-2.5" /> View
          </div>
          <div className="text-xs font-bold text-foreground">
            {formatNum(evidence.metricsSnapshot.views)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-0.5">
            <Heart className="size-2.5" /> Like
          </div>
          <div className="text-xs font-bold text-foreground">
            {formatNum(evidence.metricsSnapshot.likes)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-0.5">
            <Share2 className="size-2.5" /> Share
          </div>
          <div className="text-xs font-bold text-foreground">
            {formatNum(evidence.metricsSnapshot.shares)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-0.5">
            <TrendingUp className="size-2.5" /> ER
          </div>
          <div className="text-xs font-bold text-primary">
            {evidence.metricsSnapshot.engagementRate}%
          </div>
        </div>
      </div>

      {/* Reason why relevant */}
      <div className="text-xs text-muted-foreground bg-accent/20 p-2.5 rounded-lg border border-accent/30 leading-relaxed">
        <span className="font-semibold text-foreground text-[11px] block mb-0.5">
          Tại sao bằng chứng này quan trọng:
        </span>
        {evidence.reason}
      </div>

      <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[11px]">
        <span className="text-muted-foreground flex items-center gap-1">
          <Clock className="size-3" /> Xuất bản: {new Date(evidence.publishedAt).toLocaleDateString("vi-VN")}
        </span>
        <a
          href={evidence.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
        >
          <span>Xem bài gốc</span>
          <ExternalLink className="size-3" />
        </a>
      </div>
    </div>
  );
}
