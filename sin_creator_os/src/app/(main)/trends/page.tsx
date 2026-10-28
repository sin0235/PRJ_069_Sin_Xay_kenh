"use client";

import { Activity } from "lucide-react";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

export default function EmptyDataPage() {
  return (
    <div className="p-6">
      <Empty className="min-h-80 border">
        <EmptyHeader>
          <EmptyMedia variant="icon"><Activity aria-hidden="true" /></EmptyMedia>
          <EmptyTitle>Chưa có dữ liệu thực</EmptyTitle>
          <EmptyDescription>Trang này sẽ hiển thị nội dung khi hệ thống có dữ liệu thật từ nguồn kết nối.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </div>
  );
}
