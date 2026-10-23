"use client";

import * as React from "react";
import {
  Server,
  ShieldCheck,
  ShieldAlert,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Key,
  Eye,
  EyeOff,
  RefreshCw,
  Power,
  Sliders,
  Clock,
  Layers,
  Coins,
  DollarSign,
  Film,
  Music,
  Video,
  Lock,
  ExternalLink,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

import {
  PlatformConfigService,
  PlatformLLMConfig,
  PlatformLLMConfigUpdate,
  PlatformLLMProbeResult,
  PlatformLLMPublicStatus,
} from "@/services";

export default function IntegrationsPage() {
  const [activeTab, setActiveTab] = React.useState<string>("llm_gateway");
  const [loading, setLoading] = React.useState<boolean>(true);
  const [isOwner, setIsOwner] = React.useState<boolean>(true);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  // Dữ liệu LLM Config (Dành cho Owner)
  const [config, setConfig] = React.useState<PlatformLLMConfig | null>(null);

  // Dữ liệu Public Status (Dành cho Non-Owner)
  const [publicStatus, setPublicStatus] = React.useState<PlatformLLMPublicStatus | null>(null);

  // Form State
  const [baseUrl, setBaseUrl] = React.useState<string>("http://127.0.0.1:20128/v1");
  const [model, setModel] = React.useState<string>("gpt-4o-mini");
  const [newApiKey, setNewApiKey] = React.useState<string>("");
  const [showKey, setShowKey] = React.useState<boolean>(false);
  const [isEnabled, setIsEnabled] = React.useState<boolean>(false);
  const [timeoutSeconds, setTimeoutSeconds] = React.useState<number>(30.0);
  const [maxOutputTokens, setMaxOutputTokens] = React.useState<number>(1500);
  const [maxInputBytes, setMaxInputBytes] = React.useState<number>(20000);
  const [inputUsd, setInputUsd] = React.useState<number>(0.00015);
  const [outputUsd, setOutputUsd] = React.useState<number>(0.00060);
  const [budgetUnits, setBudgetUnits] = React.useState<number>(100.0);

  // Probe State
  const [probing, setProbing] = React.useState<boolean>(false);
  const [probeResult, setProbeResult] = React.useState<PlatformLLMProbeResult | null>(null);

  // Saving State
  const [saving, setSaving] = React.useState<boolean>(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = React.useState<string | null>(null);

  // Modals
  const [isRotateModalOpen, setIsRotateModalOpen] = React.useState<boolean>(false);
  const [isDeactivateModalOpen, setIsDeactivateModalOpen] = React.useState<boolean>(false);

  // Tải dữ liệu ban đầu
  const loadData = React.useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await PlatformConfigService.getConfig();
      setIsOwner(true);
      setConfig(data);
      setBaseUrl(data.base_url || "http://127.0.0.1:20128/v1");
      setModel(data.model || "gpt-4o-mini");
      setIsEnabled(data.is_enabled);
      setTimeoutSeconds(data.timeout_seconds || 30.0);
      setMaxOutputTokens(data.max_output_tokens || 1500);
      setMaxInputBytes(data.max_input_bytes || 20000);
      setInputUsd(data.input_usd_per_1k_tokens || 0.00015);
      setOutputUsd(data.output_usd_per_1k_tokens || 0.00060);
      setBudgetUnits(data.budget_units_per_usd || 100.0);
    } catch (err: any) {
      if (err?.message?.includes("PERMISSION_DENIED")) {
        setIsOwner(false);
        try {
          const pub = await PlatformConfigService.getPublicStatus();
          setPublicStatus(pub);
        } catch {
          // fallback im lặng
        }
      } else {
        setErrorMsg(err?.message || "Không thể tải cấu hình cổng LLM");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Xử lý kiểm tra kết nối Probe
  const handleProbe = async () => {
    setProbing(true);
    setProbeResult(null);
    try {
      const res = await PlatformConfigService.probeGateway({
        base_url: baseUrl,
        model: model,
        probe_api_key: newApiKey.trim() ? newApiKey.trim() : null,
      });
      setProbeResult(res);
    } catch (err: any) {
      setProbeResult({
        ok: false,
        latency_ms: 0,
        status_code: null,
        message: err?.message || "Lỗi không xác định khi kết nối cổng 9Router.",
        models_discovered: [],
      });
    } finally {
      setProbing(false);
    }
  };

  // Thực thi lưu cấu hình
  const executeSave = async (overrideEnabled?: boolean) => {
    setSaving(true);
    setSaveSuccessMsg(null);
    setErrorMsg(null);

    const payload: PlatformLLMConfigUpdate = {
      is_enabled: overrideEnabled !== undefined ? overrideEnabled : isEnabled,
      base_url: baseUrl.trim(),
      model: model.trim(),
      new_api_key: newApiKey.trim() ? newApiKey.trim() : null,
      timeout_seconds: Number(timeoutSeconds),
      max_output_tokens: Number(maxOutputTokens),
      max_input_bytes: Number(maxInputBytes),
      input_usd_per_1k_tokens: Number(inputUsd),
      output_usd_per_1k_tokens: Number(outputUsd),
      budget_units_per_usd: Number(budgetUnits),
    };

    try {
      const updated = await PlatformConfigService.updateConfig(payload);
      setConfig(updated);
      setIsEnabled(updated.is_enabled);
      setNewApiKey(""); // Xóa sạch ô nhập key sau khi lưu thành công
      setSaveSuccessMsg("Đã cập nhật cấu hình Cổng LLM 9Router thành công.");
      setIsRotateModalOpen(false);
      setIsDeactivateModalOpen(false);
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi lưu cấu hình.");
    } finally {
      setSaving(false);
    }
  };

  // Nút Lưu/Cập nhật bấm
  const handleSaveClick = () => {
    if (newApiKey.trim().length > 0) {
      // Mở modal xác nhận xoay khóa
      setIsRotateModalOpen(true);
    } else {
      executeSave();
    }
  };

  // Nút Tắt cổng bấm
  const handleDeactivateClick = () => {
    setIsDeactivateModalOpen(true);
  };

  return (
    <div className="space-y-6 pb-20 max-w-5xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Tích Hợp API Nền Tảng (Integrations)
          </h1>
          <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-xs font-semibold">
            Zero Plaintext Secrets
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          Quản trị tập trung Cổng LLM 9Router toàn nền tảng, dịch vụ Media độc lập và bảo mật Secret Vault.
        </p>
      </div>

      {/* Security Callout */}
      <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-muted/40 border border-border/80 text-xs">
        <ShieldCheck className="size-4 text-emerald-500 shrink-0" />
        <span className="text-muted-foreground">
          Mọi khóa bí mật (API Key) được mã hóa đối xứng an toàn trước khi lưu trữ vào cơ sở dữ liệu. Hệ thống không bao giờ trả lại khóa dạng rõ ra giao diện.
        </span>
      </div>

      {/* Navigation Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2 h-9 p-1 bg-muted/60 rounded-xl">
          <TabsTrigger value="llm_gateway" className="text-xs font-medium flex items-center gap-2 rounded-lg">
            <Server className="size-3.5" />
            Cổng LLM 9Router
          </TabsTrigger>
          <TabsTrigger value="media_services" className="text-xs font-medium flex items-center gap-2 rounded-lg">
            <Film className="size-3.5" />
            Dịch Vụ Media & Khác
          </TabsTrigger>
        </TabsList>

        {/* ======================================================== */}
        {/* TAB 1: CỔNG LLM 9ROUTER (HỆ THỐNG)                      */}
        {/* ======================================================== */}
        <TabsContent value="llm_gateway" className="space-y-5 pt-3">
          {loading ? (
            <Card className="p-8 text-center rounded-2xl border-border/80">
              <RefreshCw className="size-6 animate-spin mx-auto text-primary mb-2" />
              <p className="text-xs text-muted-foreground">Đang tải cấu hình Cổng LLM...</p>
            </Card>
          ) : !isOwner ? (
            /* ============================================== */
            /* TRẠNG THÁI C: NON-OWNER READ-ONLY              */
            /* ============================================== */
            <Card className="rounded-2xl border-border/80 p-6 space-y-4 bg-card">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                    <Server className="size-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-foreground">
                      Cổng Dịch Vụ LLM Nền Tảng (9Router Gateway)
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Mô hình ngôn ngữ lớn được quản trị tập trung bởi Quản Trị Viên Nền Tảng (Platform Owner).
                    </p>
                  </div>
                </div>

                {publicStatus?.is_enabled ? (
                  <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 bg-emerald-500/10 text-xs">
                    <CheckCircle2 className="size-3 mr-1" />
                    Đang Hoạt Động
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-amber-500/40 text-amber-600 bg-amber-500/10 text-xs">
                    <Clock className="size-3 mr-1" />
                    Chế Độ Dự Phòng (Offline)
                  </Badge>
                )}
              </div>

              <div className="p-4 rounded-xl bg-muted/40 border border-border/60 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Mô hình phục vụ:</span>
                  <span className="font-mono font-semibold text-foreground">
                    {publicStatus?.model || "gpt-4o-mini"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Trạng thái định tuyến:</span>
                  <span className="text-foreground font-medium">
                    {publicStatus?.is_enabled ? "9Router Gateway Nội Bộ" : "Offline Rule-based Template"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Cập nhật lần cuối:</span>
                  <span className="text-muted-foreground">
                    {publicStatus?.updated_at ? new Date(publicStatus.updated_at).toLocaleString("vi-VN") : "Hệ thống"}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-400">
                <Lock className="size-4 shrink-0" />
                <span>
                  Bạn đang đăng nhập với vai trò thành viên Workspace. Biểu mẫu cấu hình Cổng LLM chỉ dành riêng cho Platform Owner.
                </span>
              </div>
            </Card>
          ) : (
            /* ============================================== */
            /* TRẠNG THÁI A & B: DÀNH CHO PLATFORM OWNER      */
            /* ============================================== */
            <div className="space-y-5">
              {/* Card Tổng Quan Trạng Thái */}
              <Card className="rounded-2xl border-border/80 p-5 bg-card space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                      <Server className="size-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-foreground">
                          Cấu Hình Cổng LLM Trung Tâm (9Router Gateway)
                        </h3>
                        <Badge variant="outline" className="border-primary/40 text-primary bg-primary/5 text-[10px] font-semibold">
                          Platform Owner
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Điểm kết nối mô hình ngôn ngữ lớn duy nhất phục vụ toàn bộ các module sinh ý tưởng và kịch bản.
                      </p>
                    </div>
                  </div>

                  {config?.is_configured && config?.is_enabled ? (
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 bg-emerald-500/10 text-xs font-semibold py-1 px-2.5">
                      <CheckCircle2 className="size-3.5 mr-1" />
                      Đang Hoạt Động (Active)
                    </Badge>
                  ) : config?.is_configured && !config?.is_enabled ? (
                    <Badge variant="outline" className="border-amber-500/40 text-amber-600 bg-amber-500/10 text-xs font-semibold py-1 px-2.5">
                      <Power className="size-3.5 mr-1" />
                      Tạm Dừng (Disabled)
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="border-muted-foreground/40 text-muted-foreground bg-muted text-xs font-semibold py-1 px-2.5">
                      <AlertCircle className="size-3.5 mr-1" />
                      Chưa Cấu Hình
                    </Badge>
                  )}
                </div>

                {/* Tóm tắt cấu hình hiện tại */}
                {config?.is_configured && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3.5 rounded-xl bg-muted/30 border border-border/60 text-xs">
                    <div>
                      <span className="text-[11px] text-muted-foreground block">Gateway Endpoint:</span>
                      <span className="font-mono text-foreground font-medium truncate block">
                        {config.base_url}
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-muted-foreground block">Mô Hình Đang Dùng:</span>
                      <span className="font-mono text-foreground font-medium">{config.model}</span>
                    </div>
                    <div>
                      <span className="text-[11px] text-muted-foreground block">Khóa Xác Thực Đã Lưu:</span>
                      <span className="font-mono text-emerald-600 dark:text-emerald-400 font-medium">
                        {config.key_fingerprint || "Chưa có khóa"}
                      </span>
                    </div>
                  </div>
                )}

                {/* Thông báo thành công / lỗi */}
                {saveSuccessMsg && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="size-4 shrink-0" />
                    <span>{saveSuccessMsg}</span>
                  </div>
                )}
                {errorMsg && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-destructive/10 border border-destructive/30 text-xs text-destructive">
                    <AlertTriangle className="size-4 shrink-0" />
                    <span>{errorMsg}</span>
                  </div>
                )}
              </Card>

              {/* Form Cấu Hình Chi Tiết */}
              <Card className="rounded-2xl border-border/80 p-5 bg-card space-y-5">
                <div className="flex items-center gap-2 pb-2 border-b border-border/60">
                  <Sliders className="size-4 text-primary" />
                  <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                    Thông Số Kết Nối & Vận Hành
                  </h4>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Field 1: Base URL */}
                  <div className="space-y-1.5 md:col-span-2">
                    <label className="text-[11px] font-semibold text-foreground block">
                      1. URL Cổng 9Router Gateway:
                    </label>
                    <Input
                      type="text"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="http://127.0.0.1:20128/v1"
                      className="h-9 text-xs font-mono rounded-xl bg-background"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Lưu ý: Môi trường nội bộ cục bộ chấp nhận 127.0.0.1 hoặc localhost; môi trường máy chủ ngoài bắt buộc giao thức HTTPS bảo mật.
                    </p>
                  </div>

                  {/* Field 2: Model */}
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-foreground block">
                      2. Định Danh Mô Hình (Model ID):
                    </label>
                    <Input
                      type="text"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="gpt-4o-mini"
                      className="h-9 text-xs font-mono rounded-xl bg-background"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Mô hình định tuyến qua 9Router (ví dụ: gpt-4o-mini, claude-3-5-sonnet).
                    </p>
                  </div>

                  {/* Field 3: API Key */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-semibold text-foreground block">
                        3. Khóa Xác Thực (API Key / Bearer Token):
                      </label>
                      {config?.has_api_key && (
                        <span className="text-[10px] text-emerald-600 font-mono">
                          Hiện tại: {config.key_fingerprint}
                        </span>
                      )}
                    </div>
                    <div className="relative">
                      <Input
                        type={showKey ? "text" : "password"}
                        value={newApiKey}
                        onChange={(e) => setNewApiKey(e.target.value)}
                        placeholder={
                          config?.has_api_key
                            ? "Để trống nếu muốn giữ nguyên khóa đã lưu..."
                            : "Nhập khóa bí mật tại đây..."
                        }
                        className="h-9 text-xs font-mono rounded-xl bg-background pr-9"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKey(!showKey)}
                        className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      Khóa được mã hóa bằng Fernet AES-256 đối xứng. Để trống để giữ nguyên khóa hiện có.
                    </p>
                  </div>
                </div>

                {/* Tham Số Vận Hành & Ngân Sách */}
                <div className="pt-2">
                  <span className="text-[11px] font-semibold text-foreground block mb-3">
                    4. Tham Số Vận Hành, Timeout & Ngân Sách:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="p-3 rounded-xl bg-muted/30 border border-border/60 space-y-1.5">
                      <label className="text-[10px] font-medium text-muted-foreground block flex items-center gap-1">
                        <Clock className="size-3" /> Thời gian chờ (Timeout):
                      </label>
                      <div className="flex items-center gap-1.5">
                        <Input
                          type="number"
                          step="1"
                          min="1"
                          max="120"
                          value={timeoutSeconds}
                          onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                          className="h-8 text-xs font-mono rounded-lg bg-background"
                        />
                        <span className="text-[11px] text-muted-foreground">giây</span>
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-muted/30 border border-border/60 space-y-1.5">
                      <label className="text-[10px] font-medium text-muted-foreground block flex items-center gap-1">
                        <Layers className="size-3" /> Token Đầu Ra Tối Đa:
                      </label>
                      <div className="flex items-center gap-1.5">
                        <Input
                          type="number"
                          step="100"
                          min="100"
                          max="8000"
                          value={maxOutputTokens}
                          onChange={(e) => setMaxOutputTokens(Number(e.target.value))}
                          className="h-8 text-xs font-mono rounded-lg bg-background"
                        />
                        <span className="text-[11px] text-muted-foreground">tokens</span>
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-muted/30 border border-border/60 space-y-1.5">
                      <label className="text-[10px] font-medium text-muted-foreground block flex items-center gap-1">
                        <Coins className="size-3" /> Đơn Vị Ngân Sách / 1 USD:
                      </label>
                      <div className="flex items-center gap-1.5">
                        <Input
                          type="number"
                          step="1"
                          min="1"
                          max="1000000"
                          value={budgetUnits}
                          onChange={(e) => setBudgetUnits(Number(e.target.value))}
                          className="h-8 text-xs font-mono rounded-lg bg-background"
                        />
                        <span className="text-[11px] text-muted-foreground">units</span>
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-muted/30 border border-border/60 space-y-1.5">
                      <label className="text-[10px] font-medium text-muted-foreground block flex items-center gap-1">
                        <DollarSign className="size-3" /> Giá Input USD / 1k Tokens:
                      </label>
                      <Input
                        type="number"
                        step="0.00001"
                        min="0"
                        value={inputUsd}
                        onChange={(e) => setInputUsd(Number(e.target.value))}
                        className="h-8 text-xs font-mono rounded-lg bg-background"
                      />
                    </div>

                    <div className="p-3 rounded-xl bg-muted/30 border border-border/60 space-y-1.5">
                      <label className="text-[10px] font-medium text-muted-foreground block flex items-center gap-1">
                        <DollarSign className="size-3" /> Giá Output USD / 1k Tokens:
                      </label>
                      <Input
                        type="number"
                        step="0.00001"
                        min="0"
                        value={outputUsd}
                        onChange={(e) => setOutputUsd(Number(e.target.value))}
                        className="h-8 text-xs font-mono rounded-lg bg-background"
                      />
                    </div>

                    <div className="p-3 rounded-xl bg-muted/30 border border-border/60 space-y-1.5">
                      <label className="text-[10px] font-medium text-muted-foreground block flex items-center gap-1">
                        <Layers className="size-3" /> Giới Hạn Input Bytes:
                      </label>
                      <div className="flex items-center gap-1.5">
                        <Input
                          type="number"
                          step="1000"
                          min="1000"
                          max="100000"
                          value={maxInputBytes}
                          onChange={(e) => setMaxInputBytes(Number(e.target.value))}
                          className="h-8 text-xs font-mono rounded-lg bg-background"
                        />
                        <span className="text-[11px] text-muted-foreground">bytes</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Trạng thái Kích Hoạt */}
                <div className="pt-2 flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="is_enabled_toggle"
                    checked={isEnabled}
                    onChange={(e) => setIsEnabled(e.target.checked)}
                    className="size-4 rounded text-primary focus:ring-primary border-border"
                  />
                  <label htmlFor="is_enabled_toggle" className="text-xs font-medium text-foreground cursor-pointer select-none">
                    Kích hoạt sử dụng Cổng LLM này ngay cho các tính năng sinh nội dung
                  </label>
                </div>

                {/* Khu Vực Probe Result */}
                {probeResult && (
                  <div
                    className={`p-3.5 rounded-xl border text-xs space-y-1.5 ${
                      probeResult.ok
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400"
                        : "bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-400"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold">
                      {probeResult.ok ? (
                        <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                      ) : (
                        <AlertCircle className="size-4 text-amber-500 shrink-0" />
                      )}
                      <span>{probeResult.message}</span>
                    </div>
                    <div className="text-[11px] flex gap-4 text-muted-foreground pt-1">
                      <span>Độ trễ: {probeResult.latency_ms}ms</span>
                      {probeResult.status_code && <span>Mã phản hồi: {probeResult.status_code}</span>}
                      {probeResult.models_discovered && probeResult.models_discovered.length > 0 && (
                        <span>Mô hình tìm thấy: {probeResult.models_discovered.join(", ")}</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Hàng Nút Hành Động */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-border/60">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleProbe}
                    disabled={probing}
                    className="h-9 text-xs rounded-xl font-medium w-full sm:w-auto"
                  >
                    {probing ? (
                      <>
                        <RefreshCw className="size-3.5 animate-spin mr-1.5" />
                        Đang Kiểm Tra Kết Nối...
                      </>
                    ) : (
                      <>
                        <Server className="size-3.5 mr-1.5" />
                        Kiểm Tra Kết Nối (Probe Gateway)
                      </>
                    )}
                  </Button>

                  <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                    {config?.is_enabled && (
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={handleDeactivateClick}
                        disabled={saving}
                        className="h-9 text-xs rounded-xl font-medium"
                      >
                        <Power className="size-3.5 mr-1.5" />
                        Tắt Cổng LLM
                      </Button>
                    )}

                    <Button
                      type="button"
                      size="sm"
                      onClick={handleSaveClick}
                      disabled={saving}
                      className="h-9 text-xs rounded-xl font-semibold bg-primary text-primary-foreground hover:bg-primary/90"
                    >
                      {saving ? (
                        <>
                          <RefreshCw className="size-3.5 animate-spin mr-1.5" />
                          Đang Lưu Cấu Hình...
                        </>
                      ) : (
                        <>
                          <Key className="size-3.5 mr-1.5" />
                          {config?.is_configured ? "Cập Nhật Cấu Hình" : "Lưu Cấu Hình Mới"}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* ======================================================== */}
        {/* TAB 2: DỊCH VỤ MEDIA & KHÁC (FLOW, TIKTOK, S3)          */}
        {/* ======================================================== */}
        <TabsContent value="media_services" className="space-y-4 pt-3">
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
              Dịch Vụ Media Độc Lập & Lưu Trữ Đám Mây
            </h3>
            <p className="text-xs text-muted-foreground">
              Các dịch vụ media vận hành trên các luồng xử lý chuyên dụng độc lập, không đi qua Cổng LLM Chat Completions.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              {/* TikTok Official API */}
              <Card className="rounded-2xl border-border/80 p-4 space-y-3 bg-card flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="size-9 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center font-mono">
                        TT
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-foreground">TikTok Official API</h4>
                        <span className="text-[10px] text-muted-foreground">Nền tảng mạng xã hội</span>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-600 bg-amber-500/10">
                      Chờ Cấp Quyền OAuth
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Kết nối tài khoản TikTok để lên lịch đăng tải video dọc 9:16 và đồng bộ dữ liệu người xem thực tế.
                  </p>
                </div>
                <div className="pt-2 border-t border-border/50 flex justify-between items-center text-xs">
                  <span className="text-[10px] text-muted-foreground">Xác thực: OAuth 2.0 PKCE</span>
                  <Button variant="outline" size="sm" className="h-7 text-xs rounded-lg">
                    Quản Lý Kết Nối
                  </Button>
                </div>
              </Card>

              {/* Flow Music / Voice */}
              <Card className="rounded-2xl border-border/80 p-4 space-y-3 bg-card flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="size-9 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center font-mono">
                        <Music className="size-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-foreground">Flow Music & Voice Engine</h4>
                        <span className="text-[10px] text-muted-foreground">Động cơ âm nhạc & thuyết minh</span>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-600 bg-emerald-500/10">
                      Sẵn Sàng (Local/NAS)
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Động cơ sinh nhạc nền và chuyển văn bản thành giọng đọc (TTS) chạy riêng biệt trên luồng tác vụ media.
                  </p>
                </div>
                <div className="pt-2 border-t border-border/50 flex justify-between items-center text-xs">
                  <span className="text-[10px] text-muted-foreground">Giao thức: Background Pipeline</span>
                  <Button variant="outline" size="sm" className="h-7 text-xs rounded-lg">
                    Thông Số Kỹ Thuật
                  </Button>
                </div>
              </Card>

              {/* Object Storage */}
              <Card className="rounded-2xl border-border/80 p-4 space-y-3 bg-card flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="size-9 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center font-mono">
                        S3
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-foreground">Cloudflare R2 / AWS S3</h4>
                        <span className="text-[10px] text-muted-foreground">Lưu trữ đám mây</span>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-600 bg-emerald-500/10">
                      Đã Cấu Hình
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Kho lưu trữ đám mây tốc độ cao lưu trữ các tập tin video 4K render và asset media đồ họa.
                  </p>
                </div>
                <div className="pt-2 border-t border-border/50 flex justify-between items-center text-xs">
                  <span className="text-[10px] text-muted-foreground font-mono">r2_bucket_baha_storage_01••••</span>
                  <Button variant="outline" size="sm" className="h-7 text-xs rounded-lg">
                    Chi Tiết Lưu Trữ
                  </Button>
                </div>
              </Card>

              {/* Video Pipeline FFmpeg */}
              <Card className="rounded-2xl border-border/80 p-4 space-y-3 bg-card flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="size-9 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center font-mono">
                        <Video className="size-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-foreground">FFmpeg Rendering Pipeline</h4>
                        <span className="text-[10px] text-muted-foreground">Xử lý video local</span>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-600 bg-emerald-500/10">
                      Sẵn Sàng
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Động cơ cắt ghép, ghép âm thanh và chèn phụ đề tự động theo chuẩn khung dọc TikTok 9:16.
                  </p>
                </div>
                <div className="pt-2 border-t border-border/50 flex justify-between items-center text-xs">
                  <span className="text-[10px] text-muted-foreground">Độ phân giải: 1080x1920 (30fps)</span>
                  <Button variant="outline" size="sm" className="h-7 text-xs rounded-lg">
                    Cấu Hình Render
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ======================================================== */}
      {/* MODAL 1: XÁC NHẬN XOAY KHÓA API (ROTATE KEY MODAL)       */}
      {/* ======================================================== */}
      <Dialog open={isRotateModalOpen} onOpenChange={setIsRotateModalOpen}>
        <DialogContent className="max-w-md rounded-2xl p-5 space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <ShieldAlert className="size-5 text-amber-500 shrink-0" />
              <DialogTitle className="text-base font-bold text-foreground">
                Xác Nhận Thay Đổi Khóa Xác Thực LLM
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground pt-1 leading-relaxed">
              Bạn đang thực hiện thay đổi Khóa Xác Thực (API Key) của Cổng LLM Toàn Nền Tảng.
            </DialogDescription>
          </DialogHeader>

          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs space-y-2 text-amber-800 dark:text-amber-300">
            <p className="font-semibold">Lưu ý bảo mật quan trọng:</p>
            <ul className="list-disc pl-4 space-y-1 text-[11px]">
              <li>Khóa mới sẽ có hiệu lực ngay lập tức cho toàn bộ các tác vụ sinh nội dung.</li>
              <li>Khóa cũ sẽ bị hủy vĩnh viễn trong cơ sở dữ liệu.</li>
              <li>Khóa mới sẽ được mã hóa an toàn và chỉ hiển thị 4 ký tự cuối.</li>
            </ul>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/60">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsRotateModalOpen(false)}
              disabled={saving}
              className="h-8 text-xs rounded-lg"
            >
              Hủy Bỏ
            </Button>
            <Button
              size="sm"
              onClick={() => executeSave()}
              disabled={saving}
              className="h-8 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {saving ? (
                <>
                  <RefreshCw className="size-3 animate-spin mr-1.5" />
                  Đang Cập Nhật...
                </>
              ) : (
                "Xác Nhận Thay Khóa"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ======================================================== */}
      {/* MODAL 2: XÁC NHẬN TẮT CỔNG LLM (DEACTIVATE MODAL)        */}
      {/* ======================================================== */}
      <Dialog open={isDeactivateModalOpen} onOpenChange={setIsDeactivateModalOpen}>
        <DialogContent className="max-w-md rounded-2xl p-5 space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-5 text-destructive shrink-0" />
              <DialogTitle className="text-base font-bold text-foreground">
                Xác Nhận Tắt Cổng LLM Hệ Thống
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground pt-1 leading-relaxed">
              Cảnh báo an toàn vận hành khi chuyển đổi chế độ sinh nội dung.
            </DialogDescription>
          </DialogHeader>

          <div className="p-3.5 rounded-xl bg-destructive/10 border border-destructive/20 text-xs space-y-2 text-destructive">
            <p className="font-semibold">Hệ quả khi tắt cổng:</p>
            <ul className="list-disc pl-4 space-y-1 text-[11px]">
              <li>Toàn bộ tính năng sinh ý tưởng tự động sẽ tạm thời chuyển sang chế độ tạo mẫu Offline Template (Rule-based).</li>
              <li>Toàn bộ cấu hình kỹ thuật và khóa xác thực vẫn được bảo lưu an toàn trong DB.</li>
              <li>Bạn có thể kích hoạt lại bất kỳ lúc nào.</li>
            </ul>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/60">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsDeactivateModalOpen(false)}
              disabled={saving}
              className="h-8 text-xs rounded-lg"
            >
              Giữ Hoạt Động
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => executeSave(false)}
              disabled={saving}
              className="h-8 text-xs font-semibold rounded-lg"
            >
              {saving ? (
                <>
                  <RefreshCw className="size-3 animate-spin mr-1.5" />
                  Đang Xử Lý...
                </>
              ) : (
                "Xác Nhận Tắt Cổng"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
