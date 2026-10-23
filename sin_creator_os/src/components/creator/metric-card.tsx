"use client";

import * as React from "react";
import { TrendingUp, TrendingDown, LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  title: string;
  value: string | number;
  changePercent?: number;
  period?: string;
  icon?: LucideIcon;
  subtext?: string;
}

export function MetricCard({
  title,
  value,
  changePercent,
  period = "so với 7 ngày trước",
  icon: Icon,
  subtext,
}: MetricCardProps) {
  const isPositive = (changePercent ?? 0) >= 0;

  return (
    <Card className="rounded-2xl border-border/80 bg-card p-4 space-y-3 shadow-xs hover:border-primary/40 transition-colors">
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-xs font-medium tracking-tight">{title}</span>
        {Icon && (
          <div className="size-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
            <Icon className="size-4" />
          </div>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-2xl font-bold tracking-tight text-foreground font-mono">
          {value}
        </div>

        {changePercent !== undefined && (
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={`inline-flex items-center gap-0.5 font-semibold px-1.5 py-0.5 rounded-md ${
                isPositive
                  ? "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                  : "text-rose-600 dark:text-rose-400 bg-rose-500/10"
              }`}
            >
              {isPositive ? (
                <TrendingUp className="size-3 stroke-[2.5]" />
              ) : (
                <TrendingDown className="size-3 stroke-[2.5]" />
              )}
              {isPositive ? `+${changePercent}%` : `${changePercent}%`}
            </span>
            <span className="text-[11px] text-muted-foreground">{period}</span>
          </div>
        )}

        {subtext && <div className="text-[11px] text-muted-foreground">{subtext}</div>}
      </div>
    </Card>
  );
}
