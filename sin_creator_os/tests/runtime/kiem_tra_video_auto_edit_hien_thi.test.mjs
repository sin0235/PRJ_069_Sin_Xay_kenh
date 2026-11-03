import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import test from "node:test";

const packageRoot = process.env.AUTO_EDIT_SOURCE_ROOT
  ?? resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(resolve(packageRoot, "package.json"));
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

test("clip Auto Edit đã lưu vẫn hiện sau khi mở lại trang và chưa chọn video nguồn", () => {
  const componentPath = process.env.AUTO_EDIT_COMPONENT_PATH
    ?? resolve(packageRoot, "src/components/video_studio/tu_dong_dung_video_dai.tsx");
  const source = readFileSync(componentPath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports = {};

  runInNewContext(compiled, {
    exports,
    require(id) {
      if (id === "react") return React;
      if (id === "react/jsx-runtime") return require(id);
      if (id === "lucide-react") return { FileVideo2: () => null, Upload: () => null, WandSparkles: () => null };
      if (id === "@/lib/api/media-studio-api") return { mediaStudioApi: {} };
      if (id === "@/lib/video_studio/phan_tich_manifest_dung_tu_dong") return { docManifestDungTuDong: () => null };
      if (id === "@/lib/video_studio/lien_ket_studio") return { taoDuongDanVideoStudio: () => "/video-studio" };
      throw new Error(`Import chưa được thay thế trong kiểm thử: ${id}`);
    },
    URL,
  });

  const assets = [
    {
      id: "source-video",
      project_id: "project-1",
      storage_key: "source.mp4",
      sha256: "source-hash",
      byte_size: 100,
      mime_detected: "video/mp4",
      source_product: "UPLOAD",
      approval_state: "UNREVIEWED",
      created_at: "2026-11-01T00:00:00Z",
    },
    {
      id: "processed-video",
      project_id: "project-1",
      storage_key: "processed.mp4",
      sha256: "processed-hash",
      byte_size: 50,
      mime_detected: "video/mp4",
      source_product: "AUTO_EDIT",
      original_filename: "clip_da_dung.mp4",
      parent_asset_id: "source-video",
      approval_state: "UNREVIEWED",
      url: "https://studio.test/v1/media/assets/processed-video/download",
      created_at: "2026-11-01T00:01:00Z",
    },
    {
      id: "processed-subtitle",
      project_id: "project-1",
      storage_key: "phu_de.srt",
      sha256: "subtitle-hash",
      byte_size: 20,
      mime_detected: "application/x-subrip",
      source_product: "AUTO_EDIT",
      original_filename: "phu_de.srt",
      parent_asset_id: "processed-video",
      approval_state: "UNREVIEWED",
      created_at: "2026-11-01T00:01:00Z",
    },
    {
      id: "processed-audio",
      project_id: "project-1",
      storage_key: "am_thanh.mp3",
      sha256: "audio-hash",
      byte_size: 20,
      mime_detected: "audio/mpeg",
      source_product: "AUTO_EDIT",
      original_filename: "am_thanh.mp3",
      parent_asset_id: "processed-video",
      approval_state: "UNREVIEWED",
      created_at: "2026-11-01T00:01:00Z",
    },
    {
      id: "processed-manifest",
      project_id: "project-1",
      storage_key: "manifest.json",
      sha256: "manifest-hash",
      byte_size: 20,
      mime_detected: "application/json",
      source_product: "AUTO_EDIT",
      original_filename: "manifest.json",
      parent_asset_id: "processed-video",
      approval_state: "UNREVIEWED",
      created_at: "2026-11-01T00:01:00Z",
    },
  ];
  for (const sourceProduct of ["AUTO_EDIT_HYPERFRAMES", "GOOGLE_FLOW"]) {
    assets.push({ ...assets[0], id: sourceProduct, source_product: sourceProduct,
      original_filename: `canh_${sourceProduct}.mp4` });
  }
  assets.push({ ...assets[0], id: "derived-upload", parent_asset_id: "source-video",
    original_filename: "ban_dan_xuat.mp4" });
  const html = renderToStaticMarkup(React.createElement(exports.TuDongDungVideoDai, {
    projectId: "project-1",
    assets,
    onAssetsChanged() {},
  }));

  assert.match(html, /clip_da_dung\.mp4/);
  assert.doesNotMatch(html, /phu_de\.srt|am_thanh\.mp3|manifest\.json/);
  assert.doesNotMatch(html, /Chỉnh trong Studio|video-studio/);
  assert.match(html, /Chờ nhân viên rà soát/);
  assert.doesNotMatch(html, /canh_AUTO_EDIT_HYPERFRAMES|canh_GOOGLE_FLOW|ban_dan_xuat/);
  assert.match(html, /value="source-video"/);
});
