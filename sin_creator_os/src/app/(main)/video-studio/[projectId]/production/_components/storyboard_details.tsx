import { Badge } from "@/components/ui/badge";
import type { ContentBrief, StoryboardShot, UiDiagram } from "@/lib/api/content-video-api";

const beatLabels = {
  HOOK: "Mở đầu",
  PAIN: "Nỗi đau",
  AGITATE: "Hệ quả",
  INSIGHT: "Kiến thức",
  SOLUTION: "Giải pháp",
  DEMO: "Minh họa",
  OUTCOME: "Kết quả",
  CTA: "Lời kêu gọi",
};
const roleLabels = { customer: "Khách hàng", ai: "Trợ lý AI", staff: "Nhân viên", system: "Hệ thống" };

export function StoryboardBrief({ brief }: { brief: ContentBrief }) {
  const groups = [
    { label: "Nỗi đau", messages: brief.pains },
    { label: "Hệ quả", messages: brief.consequences },
    { label: "Kiến thức", messages: brief.insights },
    { label: "Giải pháp", messages: brief.solutions },
    { label: "Kết quả", messages: brief.outcomes },
    { label: "Lời kêu gọi", messages: brief.cta ? [brief.cta] : [] },
  ];
  return (
    <section aria-label="Brief nội dung" className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      <div>
        <h3 className="font-semibold">Mạch nội dung</h3>
        <p className="text-muted-foreground text-sm">Kiểm tra các ý suy ra trước khi duyệt storyboard.</p>
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        {groups
          .filter((group) => group.messages.length > 0)
          .map((group) => (
            <div key={group.label} className="flex flex-col gap-1">
              <dt className="font-medium text-sm">{group.label}</dt>
              {group.messages.map((message) => (
                <dd key={message.id} className="text-muted-foreground text-sm">
                  {message.text} {message.source === "inferred" && <Badge variant="outline">Suy ra từ nội dung</Badge>}
                </dd>
              ))}
            </div>
          ))}
      </dl>
    </section>
  );
}

const layoutLabels: Record<string, string> = {
  CHAT: "Hội thoại", AI_PANEL: "Bảng AI", DASHBOARD: "Bảng thông tin",
  CHART_TARGET: "Biểu đồ so với mục tiêu", CHART_GROWTH: "Biểu đồ tăng trưởng", COMPARE_DOCS: "So sánh hai chứng từ",
  PROCESS_RAIL: "Dòng quy trình", COST_SLICE: "Bóc tách chi phí", CASH_FLOW: "Dòng tiền", STACK_HEIGHT: "Chồng hàng so với định mức",
  DOC_LAYERS: "Chứng từ nhiều tầng", END_CARD: "Thẻ kết", OPEN_NUMBER: "Mở bằng con số", OPEN_DRAIN: "Mở bằng bể cạn",
  OPEN_QUESTION: "Mở bằng câu hỏi", OPEN_HOOK: "Mở đầu", FUNNEL: "Phễu hao hụt", TIMELINE: "Lộ trình", BEFORE_AFTER: "Trước và sau",
  DONUT_SHARE: "Cơ cấu phần trăm", GAUGE: "Đồng hồ chỉ số", CHECKLIST: "Danh sách việc cần làm", HUB_SPOKE: "Gom nguồn về một nơi",
  MATRIX_2X2: "Ma trận ưu tiên", RANK_BARS: "Xếp hạng", KPI_CARDS: "Thẻ chỉ số", ASSIGN_CARDS: "Giao việc cho người",
  WAIT_CLOCK: "Khách đang chờ", RADAR_SCAN: "Quét khách tiềm năng", RACE_LANES: "So tốc độ hai cách làm", TABLE_AUDIT: "Rà bảng tìm dòng lệch",
  ALERT_STACK: "Chồng cảnh báo", PYRAMID_LEVELS: "Bậc trưởng thành", VERSUS_LIST: "So hai phương án", DOC_SEARCH: "Tìm đúng tài liệu",
};

function diagramLines(diagram: UiDiagram): string[] {
  const lines: string[] = [];
  if (diagram.steps?.length) lines.push(`Các bước: ${diagram.steps.join(" → ")}`);
  if (diagram.labels?.length) lines.push(`Nhãn: ${diagram.labels.join(" · ")}`);
  if (diagram.layers?.length) lines.push(`Ý chính: ${diagram.layers.join(" · ")}`);
  if (diagram.values?.length) lines.push(`Giá trị: ${diagram.values.join(" · ")}`);
  for (const doc of diagram.docs ?? []) lines.push(`${doc.title}: ${doc.label} · ${doc.value}`);
  for (const card of diagram.cards ?? []) lines.push(`${card.title}: ${card.label} · ${card.value}`);
  for (const item of diagram.items ?? []) lines.push(`${item.label}: ${item.value}${diagram.unit ? ` ${diagram.unit}` : ""}`);
  if (diagram.diff_label) lines.push(`Kết luận: ${diagram.diff_label}`);
  if (diagram.caption) lines.push(`Câu nhấn: ${diagram.caption}`);
  if (diagram.cta) lines.push(`Lời mời: ${diagram.cta}`);
  if (diagram.stamp) lines.push(`Dấu: ${diagram.stamp}`);
  return lines;
}

export function ShotKindBadges({ shot }: { shot: StoryboardShot }) {
  if (shot.prompt_contract_version !== 4) return null;
  return (
    <>
      {shot.beat && <Badge variant="secondary">{beatLabels[shot.beat]}</Badge>}
      <Badge variant="outline">{shot.shot_kind === "UI_SIM" ? "Dựng bằng mã" : "Clip Flow"}</Badge>
    </>
  );
}

export function ShotActionDetails({
  shot,
  onChange,
}: {
  shot: StoryboardShot;
  onChange?: (shot: StoryboardShot) => void;
}) {
  if (shot.prompt_contract_version !== 4) return null;
  const ui = shot.ui_scene;
  return (
    <div className="flex flex-col gap-3 border-t pt-3">
      {!!shot.action_beats?.length && (
        <div className="flex flex-col gap-2">
          <h4 className="font-medium text-sm">Nhịp hành động</h4>
          {shot.action_beats.map((beat, index) => (
            <div key={beat.start_s} className="text-sm">
              {onChange ? (
                <label className="grid gap-1">
                  {beat.start_s}–{beat.end_s} giây
                  <textarea
                    className="min-h-16 rounded-md border bg-background p-3"
                    maxLength={2000}
                    value={beat.action}
                    onChange={(event) =>
                      onChange({
                        ...shot,
                        action_beats: shot.action_beats?.map((item, i) =>
                          i === index ? { ...item, action: event.target.value } : item,
                        ),
                      })
                    }
                  />
                </label>
              ) : (
                <p>
                  <span className="font-medium">
                    {beat.start_s}–{beat.end_s} giây:
                  </span>{" "}
                  {beat.action}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
      {ui && ui.diagram && (
        <div className="flex flex-col gap-2">
          <h4 className="font-medium text-sm">Sơ đồ · {layoutLabels[ui.layout] ?? ui.layout}</h4>
          <p className="text-muted-foreground text-xs">
            Sơ đồ được dựng bằng mã, không tốn lượt Flow. {ui.diagram.simulated ? "Số liệu là ví dụ minh họa." : "Số liệu có nguồn."} Các
            cụm bên dưới phải khớp nguyên văn với lời thoại của cảnh để chuyển động đúng nhịp.
          </p>
          {onChange ? (
            <label className="grid gap-1 text-sm">
              Tiêu đề sơ đồ
              <input
                className="h-10 rounded-md border bg-background px-3"
                maxLength={60}
                value={ui.diagram.title}
                onChange={(event) => onChange({ ...shot, ui_scene: { ...ui, diagram: { ...ui.diagram!, title: event.target.value } } })}
              />
            </label>
          ) : (
            <p className="font-medium text-sm">{ui.diagram.title}</p>
          )}
          {diagramLines(ui.diagram).map((line) => (
            <p key={line} className="break-words text-sm">{line}</p>
          ))}
          {!!ui.diagram.on && Object.keys(ui.diagram.on).length > 0 && (
            <div className="rounded-md border bg-muted/30 p-3 text-xs">
              <p className="mb-1 font-medium">Cụm khớp với lời thoại</p>
              {Object.entries(ui.diagram.on).map(([event, phrase]) => (
                <p key={event} className="break-words"><span className="text-muted-foreground">{event}:</span> {phrase}</p>
              ))}
            </div>
          )}
        </div>
      )}
      {ui && !ui.diagram && (
        <div className="flex flex-col gap-2">
          <h4 className="font-medium text-sm">
            Chữ trên giao diện · {layoutLabels[ui.layout] ?? ui.layout}
          </h4>
          <p className="text-muted-foreground text-xs">
            Chữ hiển thị giữ số và thuật ngữ gốc. Lời thoại vẫn cần viết theo cách đọc tiếng Việt.
          </p>
          {ui.messages.map((message, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: Tin nhắn giữ nguyên thứ tự đã duyệt, chỉ sửa chữ.
            <div key={`${message.role}-${message.at_s}-${index}`} className="text-sm">
              {onChange ? (
                <label className="grid gap-1">
                  {roleLabels[message.role]} · {message.at_s} giây
                  <textarea
                    className="min-h-16 rounded-md border bg-background p-3"
                    maxLength={2000}
                    value={message.text}
                    onChange={(event) =>
                      onChange({
                        ...shot,
                        ui_scene: {
                          ...ui,
                          messages: ui.messages.map((item, i) =>
                            i === index ? { ...item, text: event.target.value } : item,
                          ),
                        },
                      })
                    }
                  />
                </label>
              ) : (
                <p className="whitespace-pre-wrap break-words">
                  <span className="font-medium">
                    {roleLabels[message.role]} · {message.at_s} giây:
                  </span>{" "}
                  {message.text}
                </p>
              )}
            </div>
          ))}
          {onChange ? (
            <label className="grid gap-1 text-sm">
              Điểm nhấn trên giao diện
              <textarea
                className="min-h-16 rounded-md border bg-background p-3"
                maxLength={1000}
                value={ui.highlight ?? ""}
                onChange={(event) =>
                  onChange({
                    ...shot,
                    ui_scene: { ...ui, highlight: event.target.value === "" ? null : event.target.value },
                  })
                }
              />
            </label>
          ) : (
            ui.highlight && <p className="font-medium text-sm">{ui.highlight}</p>
          )}
        </div>
      )}
    </div>
  );
}
