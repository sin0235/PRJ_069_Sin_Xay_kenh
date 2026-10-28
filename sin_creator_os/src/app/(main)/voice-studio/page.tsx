"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, LoaderCircle, Mic, Save, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuthApi } from "@/lib/api/auth-api";
import { mediaStudioApi } from "@/lib/api/media-studio-api";
import { voiceStudioApi, type TTSAdvancedSettings, type VoiceProfile, type VoiceStudioJob } from "@/lib/api/voice-studio-api";

const statusLabels: Record<string, string> = {
  QUEUED: "Đang chờ",
  RUNNING: "Đang tạo audio",
  SUCCEEDED: "Hoàn tất",
  FAILED: "Thất bại",
};

const defaults = {
  GWEN_TTS: { temperature: 0.3, top_k: 20, top_p: 0.9, repetition_penalty: 2, max_new_tokens: 4096, x_vector_only_mode: false },
  VIE_NEU_V3_TURBO: {
    temperature: 0.8,
    top_k: 25,
    top_p: 0.95,
    repetition_penalty: 1.2,
    denoise_reference: true,
    use_reference_codes: true,
    max_new_frames: 300,
    max_chars: 256,
  },
} satisfies Record<string, TTSAdvancedSettings>;

type Provider = keyof typeof defaults;

export default function VoiceStudioPage() {
  const [tab, setTab] = useState("tts");
  const [provider, setProvider] = useState<Provider>("VIE_NEU_V3_TURBO");
  const [voiceChoice, setVoiceChoice] = useState("preset");
  const [advanced, setAdvanced] = useState<TTSAdvancedSettings>(defaults.VIE_NEU_V3_TURBO);
  const [text, setText] = useState("");
  const [dictionary, setDictionary] = useState("");
  const [savedDictionary, setSavedDictionary] = useState("");
  const [savingDictionary, setSavingDictionary] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [jobs, setJobs] = useState<VoiceStudioJob[]>([]);
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [cloneBusy, setCloneBusy] = useState(false);
  const [error, setError] = useState("");

  const [voiceName, setVoiceName] = useState("");
  const [cloneProvider, setCloneProvider] = useState<Provider>("VIE_NEU_V3_TURBO");
  const [referenceText, setReferenceText] = useState("");
  const [referenceName, setReferenceName] = useState("");
  const [consent, setConsent] = useState(false);
  const cloneFileRef = useRef<HTMLInputElement>(null);
  const workspaceId = AuthApi.getWorkspaceId();

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await voiceStudioApi.listJobs());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không tải được lịch sử TTS.");
    }
  }, []);

  const refreshVoices = useCallback(async () => {
    try {
      setVoices(await voiceStudioApi.listVoices());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không tải được thư viện giọng.");
    }
  }, []);

  useEffect(() => {
    setSettingsLoaded(false);
    setDictionary("");
    setSavedDictionary("");
    void voiceStudioApi.getSettings().then((settings) => {
      setDictionary(settings.pronunciation_dictionary);
      setSavedDictionary(settings.pronunciation_dictionary);
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "Không tải được bộ phiên âm đã lưu."))
      .finally(() => setSettingsLoaded(true));
    void refreshJobs();
    void refreshVoices();
  }, [workspaceId, refreshJobs, refreshVoices]);

  useEffect(() => {
    if (!activeJobId) return;
    let stopped = false;
    const poll = async () => {
      try {
        const job = await voiceStudioApi.getJob(activeJobId);
        if (stopped) return;
        setJobs((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)]);
        if (job.state === "SUCCEEDED" || job.state === "FAILED") {
          setActiveJobId("");
          setBusy(false);
          if (job.state === "SUCCEEDED") await refreshJobs();
          return;
        }
      } catch (cause) {
        if (!stopped) {
          setError(cause instanceof Error ? cause.message : "Không đọc được trạng thái tác vụ.");
          setActiveJobId("");
          setBusy(false);
        }
      }
      if (!stopped) window.setTimeout(poll, 2500);
    };
    const timer = window.setTimeout(poll, 1000);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [activeJobId, refreshJobs]);

  const submitTTS = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const profile = voices.find((voice) => voice.id === voiceChoice);
      const job = await voiceStudioApi.createJob({
        provider,
        text,
        voice_id: voiceChoice === "preset" ? "Hải Đăng" : undefined,
        voice_profile_id: profile?.id,
        voice_clone_consent: false,
        pronunciation_dictionary: dictionary,
        advanced,
        idempotency_key: Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join(""),
      });
      setJobs((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)]);
      setActiveJobId(job.job_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không gửi được yêu cầu TTS.");
      setBusy(false);
    }
  };

  const saveDictionary = async () => {
    setSavingDictionary(true);
    setError("");
    try {
      const settings = await voiceStudioApi.saveSettings({ pronunciation_dictionary: dictionary });
      setDictionary(settings.pronunciation_dictionary);
      setSavedDictionary(settings.pronunciation_dictionary);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không lưu được bộ phiên âm.");
    } finally {
      setSavingDictionary(false);
    }
  };

  const saveVoice = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCloneBusy(true);
    setError("");
    try {
      const file = cloneFileRef.current?.files?.[0];
      if (!file) throw new Error("Chọn audio tham chiếu trước khi lưu giọng.");
      const reference = await mediaStudioApi.uploadAsset({
        file,
        expected_category: "audio",
        source_product: "VOICE_STUDIO_REFERENCE",
      });
      await voiceStudioApi.createVoice({
        name: voiceName,
        provider: cloneProvider,
        reference_asset_id: reference.id,
        reference_text: cloneProvider === "GWEN_TTS" ? referenceText : referenceText || undefined,
        voice_clone_consent: true,
      });
      setVoiceName("");
      setReferenceText("");
      setReferenceName("");
      setConsent(false);
      if (cloneFileRef.current) cloneFileRef.current.value = "";
      await refreshVoices();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không lưu được giọng.");
    } finally {
      setCloneBusy(false);
    }
  };

  const preparePlayback = async (job: VoiceStudioJob) => {
    if (!job.asset?.url) return;
    try {
      const playbackUrl = await mediaStudioApi.createAssetObjectUrl(job.asset.url);
      setJobs((current) => current.map((item) => item.job_id === job.job_id ? { ...item, playback_url: playbackUrl } : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không mở được audio.");
    }
  };

  const selectSavedVoice = (voice: VoiceProfile) => {
    setProvider(voice.provider);
    setAdvanced(defaults[voice.provider]);
    setVoiceChoice(voice.id);
    setTab("tts");
  };

  const changeProvider = (nextProvider: Provider) => {
    setProvider(nextProvider);
    setAdvanced(defaults[nextProvider]);
    setVoiceChoice(nextProvider === "VIE_NEU_V3_TURBO" ? "preset" : "");
  };

  const usableVoices = voices.filter((voice) => voice.provider === provider);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Mic className="size-4" /> Studio âm thanh</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Voice Clone &amp; TTS</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">Tạo audio bằng giọng có sẵn hoặc quản lý giọng clone của workspace.</p>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="gap-5">
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="tts">TTS</TabsTrigger>
          <TabsTrigger value="clone">Clone giọng</TabsTrigger>
        </TabsList>

        <TabsContent value="tts" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Chuyển văn bản thành giọng nói</CardTitle>
              <CardDescription>Chọn model và giọng đọc. Thiết lập nâng cao được áp dụng cho lần tạo này.</CardDescription>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-5" onSubmit={submitTTS}>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="tts-provider">Model TTS</Label>
                    <select id="tts-provider" value={provider} onChange={(event) => changeProvider(event.target.value as Provider)} className="h-10 rounded-md border border-input bg-background px-3 text-sm">
                      <option value="VIE_NEU_V3_TURBO">VieNeu v3 Turbo</option>
                      <option value="GWEN_TTS">Gwen-TTS</option>
                    </select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="tts-voice">Giọng đọc</Label>
                    <select id="tts-voice" value={voiceChoice} onChange={(event) => setVoiceChoice(event.target.value)} className="h-10 rounded-md border border-input bg-background px-3 text-sm">
                      {provider === "VIE_NEU_V3_TURBO" && <option value="preset">Giọng có sẵn: Hải Đăng</option>}
                      {usableVoices.map((voice) => <option key={voice.id} value={voice.id}>{voice.name}</option>)}
                    </select>
                    {provider === "GWEN_TTS" && usableVoices.length === 0 && <p className="text-xs text-muted-foreground">Lưu voice Gwen trong tab Clone giọng trước khi tạo TTS.</p>}
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="tts-text">Nội dung cần đọc</Label>
                  <textarea id="tts-text" required maxLength={5000} rows={7} value={text} onChange={(event) => setText(event.target.value)} placeholder="Nhập nội dung tiếng Việt cần chuyển thành giọng nói..." className="min-h-36 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
                  <span className="text-right text-xs text-muted-foreground">{text.length}/5000</span>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="pronunciation-dictionary">Bảng phiên âm tiếng Anh sang cách đọc tiếng Việt</Label>
                  <textarea id="pronunciation-dictionary" maxLength={10000} rows={4} value={dictionary} onChange={(event) => setDictionary(event.target.value)} placeholder={"OpenAI = âu pần ai\nGPT-4 = gi pi ti bốn"} className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm" />
                  <p className="text-xs text-muted-foreground">Mỗi dòng một mục theo dạng từ gốc = cách đọc. Bộ phiên âm được lưu cho workspace này và tự áp dụng cho các lần tạo TTS.</p>
                  <div className="flex items-center gap-3">
                    <Button type="button" variant="outline" size="sm" disabled={savingDictionary || dictionary === savedDictionary} onClick={() => void saveDictionary()}>
                      {savingDictionary ? <LoaderCircle className="mr-2 size-4 animate-spin" /> : <Save className="mr-2 size-4" />}
                      Lưu bộ phiên âm
                    </Button>
                    {dictionary === savedDictionary && <span className="text-xs text-muted-foreground">Đã lưu cho workspace</span>}
                  </div>
                </div>

                <details className="rounded-lg border p-4">
                  <summary className="cursor-pointer font-medium">Cài đặt nâng cao</summary>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <NumberSetting label="Temperature" value={advanced.temperature} min={0.1} max={1.5} step={0.05} onChange={(value) => setAdvanced((current) => ({ ...current, temperature: value }))} />
                    <NumberSetting label="Top K" value={advanced.top_k} min={1} max={100} step={1} onChange={(value) => setAdvanced((current) => ({ ...current, top_k: value }))} />
                    <NumberSetting label="Top P" value={advanced.top_p} min={0.01} max={1} step={0.01} onChange={(value) => setAdvanced((current) => ({ ...current, top_p: value }))} />
                    <NumberSetting label="Repetition penalty" value={advanced.repetition_penalty} min={1} max={2.5} step={0.05} onChange={(value) => setAdvanced((current) => ({ ...current, repetition_penalty: value }))} />
                    {provider === "GWEN_TTS" ? <>
                      <NumberSetting label="Max new tokens" value={advanced.max_new_tokens} min={64} max={8192} step={64} onChange={(value) => setAdvanced((current) => ({ ...current, max_new_tokens: value }))} />
                      <CheckSetting label="Chỉ dùng embedding giọng" checked={advanced.x_vector_only_mode || false} onChange={(value) => setAdvanced((current) => ({ ...current, x_vector_only_mode: value }))} />
                    </> : <>
                      <NumberSetting label="Max new frames" value={advanced.max_new_frames} min={50} max={1000} step={10} onChange={(value) => setAdvanced((current) => ({ ...current, max_new_frames: value }))} />
                      <NumberSetting label="Độ dài chunk (ký tự)" value={advanced.max_chars} min={32} max={512} step={8} onChange={(value) => setAdvanced((current) => ({ ...current, max_chars: value }))} />
                      <CheckSetting label="Khử nhiễu audio tham chiếu" checked={advanced.denoise_reference ?? true} onChange={(value) => setAdvanced((current) => ({ ...current, denoise_reference: value }))} />
                      <CheckSetting label="Dùng reference codes" checked={advanced.use_reference_codes ?? true} onChange={(value) => setAdvanced((current) => ({ ...current, use_reference_codes: value }))} />
                    </>}
                  </div>
                </details>

                {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
                <Button type="submit" disabled={!settingsLoaded || busy || !text.trim() || !voiceChoice || (provider === "GWEN_TTS" && !usableVoices.some((voice) => voice.id === voiceChoice))}>
                  {busy ? <><LoaderCircle className="size-4 animate-spin" /> Đang xử lý</> : "Tạo audio"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Lịch sử TTS</CardTitle><CardDescription>Audio đã tạo trong workspace.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              {jobs.length === 0 ? <p className="text-sm text-muted-foreground">Chưa có tác vụ TTS nào.</p> : jobs.map((job) => (
                <div key={job.job_id} className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 font-medium"><span>{job.provider === "GWEN_TTS" ? "Gwen-TTS" : "VieNeu v3 Turbo"}</span><Badge variant={job.state === "FAILED" ? "destructive" : "secondary"}>{statusLabels[job.state] || job.state}</Badge></div>
                    {job.error_message && <p className="text-sm text-destructive">{job.error_message}</p>}
                    {job.asset && <p className="text-xs text-muted-foreground">{job.asset.original_filename} · {(job.asset.duration_ms / 1000).toFixed(1)} giây</p>}
                  </div>
                  {job.asset && <div className="flex flex-wrap items-center gap-3">
                    {job.playback_url ? <audio controls src={job.playback_url} className="h-9 max-w-full" /> : <Button type="button" variant="outline" size="sm" onClick={() => void preparePlayback(job)}>Nghe thử</Button>}
                    <Button type="button" variant="outline" size="sm" onClick={() => void mediaStudioApi.downloadAsset(job.asset!.url, job.asset!.original_filename)}><Download className="size-4" /> Tải xuống</Button>
                  </div>}
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="clone" className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Lưu voice clone</CardTitle><CardDescription>Tạo một voice để chọn lại trong tab TTS, không phát sinh audio ở bước lưu.</CardDescription></CardHeader>
            <CardContent>
              <form className="grid gap-5 lg:grid-cols-2" onSubmit={saveVoice}>
                <div className="grid content-start gap-4">
                  <div className="grid gap-2"><Label htmlFor="voice-name">Tên giọng trong thư viện</Label><Input id="voice-name" required maxLength={100} value={voiceName} onChange={(event) => setVoiceName(event.target.value)} placeholder="Ví dụ: Giọng dẫn kênh chính" /></div>
                  <div className="grid gap-2"><Label htmlFor="clone-provider">Model clone</Label><select id="clone-provider" value={cloneProvider} onChange={(event) => setCloneProvider(event.target.value as Provider)} className="h-10 rounded-md border border-input bg-background px-3 text-sm"><option value="VIE_NEU_V3_TURBO">VieNeu v3 Turbo</option><option value="GWEN_TTS">Gwen-TTS</option></select></div>
                  <div className="grid gap-2"><Label htmlFor="clone-reference-audio">Audio mẫu</Label><Input ref={cloneFileRef} id="clone-reference-audio" type="file" accept="audio/*,.wav,.mp3,.m4a" required onChange={(event) => setReferenceName(event.target.files?.[0]?.name || "")} />{referenceName && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Upload className="size-4" />{referenceName}</p>}</div>
                </div>
                <div className="flex flex-col gap-4">
                  {cloneProvider === "GWEN_TTS" && <div className="grid gap-2"><Label htmlFor="clone-reference-text">Bản chép lời chính xác của audio mẫu</Label><textarea id="clone-reference-text" required rows={5} value={referenceText} onChange={(event) => setReferenceText(event.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></div>}
                  {cloneProvider === "VIE_NEU_V3_TURBO" && <div className="grid gap-2"><Label htmlFor="clone-reference-text">Bản chép lời audio mẫu (tùy chọn)</Label><textarea id="clone-reference-text" rows={5} value={referenceText} onChange={(event) => setReferenceText(event.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></div>}
                  <label className="flex items-start gap-2 text-sm"><input type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1" /><span>Tôi xác nhận có quyền sử dụng bản ghi này để clone giọng.</span></label>
                  <p className="text-xs text-muted-foreground">Voice đã lưu tham chiếu đến audio trong Thư viện tư liệu workspace. Gwen cần bản chép lời để clone.</p>
                  {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
                  <Button type="submit" disabled={cloneBusy || !consent}>{cloneBusy ? <><LoaderCircle className="size-4 animate-spin" /> Đang lưu</> : <><Save className="size-4" /> Lưu vào Giọng của tôi</>}</Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Giọng của tôi</CardTitle><CardDescription>Voice clone đã lưu trong workspace, có thể chọn để tạo TTS.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              {voices.length === 0 ? <p className="text-sm text-muted-foreground">Chưa có giọng nào được lưu.</p> : voices.map((voice) => (
                <div key={voice.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div><div className="font-medium">{voice.name}</div><div className="mt-1 text-xs text-muted-foreground">{voice.provider === "GWEN_TTS" ? "Gwen-TTS" : "VieNeu v3 Turbo"}{voice.reference_filename ? ` · ${voice.reference_filename}` : ""}{voice.duration_ms ? ` · ${(voice.duration_ms / 1000).toFixed(1)} giây` : ""}</div></div>
                  <Button type="button" variant="outline" size="sm" onClick={() => selectSavedVoice(voice)}>Dùng trong TTS</Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function NumberSetting({ label, value, min, max, step, onChange }: { label: string; value?: number; min: number; max: number; step: number; onChange: (value: number) => void }) {
  return <label className="grid gap-2 text-sm font-medium">{label}<Input type="number" min={min} max={max} step={step} value={value ?? ""} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function CheckSetting({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>{label}</span></label>;
}
