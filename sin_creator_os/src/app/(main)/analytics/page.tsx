"use client";

import { BarChart3 } from "lucide-react";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

export default function AnalyticsPage() {
  return (
    <div className="p-6">
      <Empty className="min-h-80 border">
        <EmptyHeader>
          <EmptyMedia variant="icon"><BarChart3 aria-hidden="true" /></EmptyMedia>
          <EmptyTitle>Chưa có dữ liệu phân tích</EmptyTitle>
          <EmptyDescription>Biểu đồ sẽ xuất hiện sau khi có số liệu hiệu suất thực từ các kênh đã kết nối.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </div>
  );
}
