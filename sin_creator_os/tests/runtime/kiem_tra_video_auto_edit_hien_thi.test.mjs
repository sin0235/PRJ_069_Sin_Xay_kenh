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
  ];
  const html = renderToStaticMarkup(React.createElement(exports.TuDongDungVideoDai, {
    projectId: "project-1",
    assets,
    onAssetsChanged() {},
  }));

  assert.match(html, /clip_da_dung\.mp4/);
  assert.match(html, /Chờ nhân viên rà soát/);
});
