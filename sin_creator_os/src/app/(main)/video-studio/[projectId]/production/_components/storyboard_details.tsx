import { Badge } from "@/components/ui/badge";
import type { ContentBrief, StoryboardShot } from "@/lib/api/content-video-api";

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

export function ShotKindBadges({ shot }: { shot: StoryboardShot }) {
  if (shot.prompt_contract_version !== 4) return null;
  return (
    <>
      {shot.beat && <Badge variant="secondary">{beatLabels[shot.beat]}</Badge>}
      <Badge variant="outline">{shot.shot_kind === "UI_SIM" ? "Mô phỏng giao diện" : "Hoạt hình giấy"}</Badge>
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
                    maxLength={1000}
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
      {ui && (
        <div className="flex flex-col gap-2">
          <h4 className="font-medium text-sm">
            Chữ trên giao diện · {{ CHAT: "Hội thoại", AI_PANEL: "Bảng AI", DASHBOARD: "Bảng thông tin" }[ui.layout]}
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
                    maxLength={1000}
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
                maxLength={500}
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
