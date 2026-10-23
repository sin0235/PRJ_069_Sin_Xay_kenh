"use client";

import * as React from "react";
import {
  Building2,
  CheckCircle2,
  History,
  Lock,
  Network,
  Shield,
  Users,
  UserPlus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function DataNotConnected({ title }: { title: string }) {
  return (
    <Card className="rounded-xl border shadow-xs">
      <CardHeader className="bg-muted/20 border-b pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm font-bold">{title}</CardTitle>
          <Badge variant="outline">Chưa kết nối</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <p className="text-sm text-muted-foreground">
          Chưa kết nối dữ liệu tổ chức. Liên hệ quản trị viên để thiết lập kết nối.
        </p>
      </CardContent>
    </Card>
  );
}

export default function TeamManagementPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-20">
      <div className="flex flex-col justify-between gap-4 border-b pb-5 md:flex-row md:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground">
              <Shield className="size-6 text-primary" />
              <span>Quản trị tổ chức và phân quyền doanh nghiệp</span>
            </h1>
            <Badge variant="outline" className="border-primary/40 bg-primary/5 text-xs font-semibold text-primary">
              BAHA-AUTHZ-001
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Quản lý thành viên, cơ cấu tổ chức và quyền truy cập.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs" disabled>
            <Building2 className="size-3.5" />
            <span>Thêm phòng ban</span>
          </Button>
          <Button size="sm" className="h-8 gap-1.5 rounded-lg text-xs" disabled>
            <UserPlus className="size-3.5" />
            <span>Mời thành viên</span>
          </Button>
        </div>
      </div>

      <Tabs defaultValue="members" className="space-y-6">
        <TabsList className="flex flex-wrap gap-1 rounded-xl border bg-muted/40 p-1">
          <TabsTrigger value="members" className="gap-1.5 py-1.5 text-xs font-semibold">
            <Users className="size-3.5" />
            <span>Thành viên và vai trò</span>
          </TabsTrigger>
          <TabsTrigger value="hierarchy" className="gap-1.5 py-1.5 text-xs font-semibold">
            <Network className="size-3.5" />
            <span>Sơ đồ tổ chức</span>
          </TabsTrigger>
          <TabsTrigger value="matrix" className="gap-1.5 py-1.5 text-xs font-semibold">
            <Lock className="size-3.5" />
            <span>Ma trận quyền</span>
          </TabsTrigger>
          <TabsTrigger value="inbox" className="gap-1.5 py-1.5 text-xs font-semibold">
            <CheckCircle2 className="size-3.5" />
            <span>Hòm thư phê duyệt</span>
          </TabsTrigger>
          <TabsTrigger value="audit" className="gap-1.5 py-1.5 text-xs font-semibold">
            <History className="size-3.5" />
            <span>Nhật ký kiểm toán</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="members" className="space-y-4">
          <DataNotConnected
            title="Danh sách thành viên và quyền được gán"
          />
        </TabsContent>
        <TabsContent value="hierarchy" className="space-y-4">
          <DataNotConnected
            title="Cơ cấu phòng ban và nhóm"
          />
        </TabsContent>
        <TabsContent value="matrix" className="space-y-4">
          <DataNotConnected
            title="Ma trận quyền hạn"
          />
        </TabsContent>
        <TabsContent value="inbox" className="space-y-4">
          <DataNotConnected
            title="Hòm thư phê duyệt"
          />
        </TabsContent>
        <TabsContent value="audit" className="space-y-4">
          <DataNotConnected
            title="Nhật ký quyết định phân quyền"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
