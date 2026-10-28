"use client";

import { Users } from "lucide-react";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

export default function AudiencePage() {
  return (
    <div className="p-6">
      <Empty className="min-h-80 border">
        <EmptyHeader>
          <EmptyMedia variant="icon"><Users aria-hidden="true" /></EmptyMedia>
          <EmptyTitle>Chưa có dữ liệu khán giả</EmptyTitle>
          <EmptyDescription>Thông tin nhân khẩu học sẽ xuất hiện khi có số liệu thực từ kênh đã kết nối.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </div>
  );
}
