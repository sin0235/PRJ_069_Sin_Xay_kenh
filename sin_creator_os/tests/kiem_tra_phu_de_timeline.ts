import * as assert from "node:assert/strict";
import { taoPhuDeDeLuu } from "../src/app/(main)/video-studio/[projectId]/phu_de_timeline";

const cues = [
  { caption_id: "cue-1", text: "Câu đầu", start_ms: 250, duration_ms: 1250, font_size: 52, safe_zone: true },
  { caption_id: "cue-2", text: "Câu tiếp", start_ms: 1500, duration_ms: 1000, font_size: 52, safe_zone: true },
];

assert.deepEqual(taoPhuDeDeLuu(cues, "Tiêu đề đã sửa", 56, 5000), [
  { ...cues[0], text: "Tiêu đề đã sửa", font_size: 56 },
  { ...cues[1], font_size: 56 },
]);
assert.deepEqual(taoPhuDeDeLuu([], "  ", 26, 3000), []);
assert.deepEqual(taoPhuDeDeLuu([], "Tiêu đề mới", 26, 5000), [
  { caption_id: "cap_main", text: "Tiêu đề mới", start_ms: 0, duration_ms: 5000, font_size: 26, safe_zone: true },
]);

console.log("Đạt: giữ nguyên mốc Vietsub, sửa được câu đầu và không tạo phụ đề giả.");
