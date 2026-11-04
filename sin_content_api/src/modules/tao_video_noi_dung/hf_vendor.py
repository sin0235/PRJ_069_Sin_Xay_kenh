"""Quản lý các thư viện vendor JS và tài nguyên cục bộ cho HyperFrames blocks.

Bảo đảm mọi khối HyperFrames dựng sẵn hoạt động độc lập (self-contained),
không còn bất kỳ URL từ xa nào (CDN, Google Fonts, @font-face ngoài) lọt vào
bản dựng composition.
"""
from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VendorReport:
    files: tuple[str, ...]      # Các tệp vendor mà khối cần (chỉ tên tệp)
    removed: tuple[str, ...]    # Các URL ngoài đã bị bóc tách
    unresolved: tuple[str, ...] # Các URL ngoài còn sót lại chưa xử lý


# Ánh xạ marker không dùng regex trong URL tới tên tệp cục bộ dưới engines/vendor
VENDOR_LIBS: dict[str, str] = {
    "gsap.min.js": "gsap.min.js",
    "CustomEase.min.js": "CustomEase.min.js",
    "d3.min.js": "d3.min.js",
    "topojson-client.min.js": "topojson-client.min.js",
    "d3-delaunay.min.js": "d3-delaunay.min.js",
    "lottie_light.min.js": "lottie_light.min.js",
    "clipper.js": "clipper.js",
}

# URL tải nguồn từ CDN jsdelivr cho các tệp thư viện
VENDOR_DOWNLOAD_URLS: dict[str, str] = {
    "gsap.min.js": "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js",
    "CustomEase.min.js": "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/CustomEase.min.js",
    "d3.min.js": "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js",
    "topojson-client.min.js": "https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js",
    "d3-delaunay.min.js": "https://cdn.jsdelivr.net/npm/d3-delaunay@6/dist/d3-delaunay.min.js",
    "lottie_light.min.js": "https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/build/player/lottie_light.min.js",
    "clipper.js": "https://cdn.jsdelivr.net/npm/clipper-lib@6.4.2/clipper.js",
}

_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")

# Vị trí: src=, href=, @import, url(...), import("..."), fetch("...")
_SRC_HREF_RE = re.compile(
    r'\b(?:src|href)\s*=\s*(?:"(?P<q1>[^"]+)"|\'(?P<q2>[^\']+)\'|(?P<uq>[^\s>"\']+))',
    re.IGNORECASE,
)
_IMPORT_RULE_RE = re.compile(
    r'@import\s+(?:url\s*\(\s*(?:"(?P<q1>[^"]+)"|\'(?P<q2>[^\']+)\'|(?P<uq>[^\s\)\'"]+))\s*\)|"(?P<q3>[^"]+)"|\'(?P<q4>[^\']+)\')\s*;?',
    re.IGNORECASE,
)
_CSS_URL_RE = re.compile(
    r'\burl\s*\(\s*(?:"(?P<q1>[^"]+)"|\'(?P<q2>[^\']+)\'|(?P<uq>[^\s\)\'"]+))\s*\)',
    re.IGNORECASE,
)
_IMPORT_FETCH_CALL_RE = re.compile(
    r'\b(?:import|fetch)\s*\(\s*(?:"(?P<q1>[^"]+)"|\'(?P<q2>[^\']+)\'|`(?P<q3>[^`]+)`)\s*[\),]',
    re.IGNORECASE,
)

# Thẻ <script ...>
_SCRIPT_TAG_RE = re.compile(
    r'<script\b(?P<attrs>[^>]*)(?:>(?P<body>(?:(?!<script\b)[\s\S])*?)</script\s*>|>|/>)\s*',
    re.IGNORECASE,
)

# Thẻ <link ...>
_LINK_TAG_RE = re.compile(
    r'<link\b[^>]*(?:/>|>)\s*',
    re.IGNORECASE,
)

# Khối @font-face
_FONT_FACE_RE = re.compile(
    r'@font-face\s*\{(?P<body>[^{}]*)\}\s*',
    re.IGNORECASE,
)


def _vendor_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "engines" / "vendor"


def _is_ignored_url(url: str) -> bool:
    if not (url.startswith("http://") or url.startswith("https://")):
        return True
    if url.startswith("http://www.w3.org/") or url.startswith("https://www.w3.org/"):
        return True
    return False


def _resolve_vendor_lib(url: str) -> str | None:
    for marker, filename in sorted(VENDOR_LIBS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if marker in url:
            return filename
    return None


def scan_external(text: str) -> list[str]:
    """Tìm tất cả các URL ngoài http(s) trong các vị trí src=, href=, @import, url(...), import("..."), fetch("...").

    Bỏ qua: URL trong HTML comment <!-- -->, giá trị thuộc tính xmlns, và URL bắt đầu bằng http://www.w3.org/.
    Giữ thứ tự xuất hiện đầu tiên, không trùng lặp.
    """
    clean = _HTML_COMMENT_RE.sub("", text)

    matches: list[tuple[int, str]] = []

    for m in _SRC_HREF_RE.finditer(clean):
        val = m.group("q1") or m.group("q2") or m.group("uq") or ""
        val = val.strip()
        if not _is_ignored_url(val):
            matches.append((m.start(), val))

    for m in _IMPORT_RULE_RE.finditer(clean):
        val = m.group("q1") or m.group("q2") or m.group("uq") or m.group("q3") or m.group("q4") or ""
        val = val.strip()
        if not _is_ignored_url(val):
            matches.append((m.start(), val))

    for m in _CSS_URL_RE.finditer(clean):
        val = m.group("q1") or m.group("q2") or m.group("uq") or ""
        val = val.strip()
        if not _is_ignored_url(val):
            matches.append((m.start(), val))

    for m in _IMPORT_FETCH_CALL_RE.finditer(clean):
        val = m.group("q1") or m.group("q2") or m.group("q3") or ""
        val = val.strip()
        if not _is_ignored_url(val):
            matches.append((m.start(), val))

    matches.sort(key=lambda item: item[0])

    seen: set[str] = set()
    result: list[str] = []
    for _, url in matches:
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


def localize(text: str) -> tuple[str, VendorReport]:
    """Bóc tách các tài nguyên ngoài khỏi nội dung khối HyperFrames.

    (a) Bỏ <script src=remote> đối với các thư viện trong VENDOR_LIBS.
    (b) Bỏ <link> tới font/stylesheet ngoài.
    (c) Bỏ các quy tắc @import url(remote).
    (d) Bỏ toàn bộ các quy tắc @font-face có src chứa url() từ xa.
    Các thư viện ngoài không nằm trong VENDOR_LIBS được giữ lại trong `unresolved`.
    """
    files_needed: list[str] = []
    removed_urls: list[str] = []

    # (a) <script src=remote>
    def replace_script(m: re.Match) -> str:
        attrs = m.group("attrs") or ""
        src_match = re.search(r'\bsrc\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))', attrs, re.IGNORECASE)
        if not src_match:
            return m.group(0)
        url = (src_match.group(1) or src_match.group(2) or src_match.group(3) or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return m.group(0)
        lib_name = _resolve_vendor_lib(url)
        if lib_name:
            if lib_name not in files_needed:
                files_needed.append(lib_name)
            if url not in removed_urls:
                removed_urls.append(url)
            return ""
        return m.group(0)

    text = _SCRIPT_TAG_RE.sub(replace_script, text)

    # (b) <link> tới fonts/stylesheets ngoài
    def replace_link(m: re.Match) -> str:
        tag = m.group(0)
        href_match = re.search(r'\bhref\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))', tag, re.IGNORECASE)
        if not href_match:
            return tag
        url = (href_match.group(1) or href_match.group(2) or href_match.group(3) or "").strip()
        if url.startswith("http://") or url.startswith("https://"):
            if url not in removed_urls:
                removed_urls.append(url)
            return ""
        return tag

    text = _LINK_TAG_RE.sub(replace_link, text)

    # (c) @import url(remote)
    def replace_import(m: re.Match) -> str:
        url = (m.group("q1") or m.group("q2") or m.group("uq") or m.group("q3") or m.group("q4") or "").strip()
        if url.startswith("http://") or url.startswith("https://"):
            if url not in removed_urls:
                removed_urls.append(url)
            return ""
        return m.group(0)

    text = _IMPORT_RULE_RE.sub(replace_import, text)

    # (d) @font-face có src là remote url()
    def replace_font_face(m: re.Match) -> str:
        body = m.group("body")
        urls_in_face: list[str] = []
        for url_match in _CSS_URL_RE.finditer(body):
            val = (url_match.group("q1") or url_match.group("q2") or url_match.group("uq") or "").strip()
            if val.startswith("http://") or val.startswith("https://"):
                urls_in_face.append(val)
        if urls_in_face:
            for u in urls_in_face:
                if u not in removed_urls:
                    removed_urls.append(u)
            return ""
        return m.group(0)

    text = _FONT_FACE_RE.sub(replace_font_face, text)

    unresolved_urls = tuple(scan_external(text))
    report = VendorReport(
        files=tuple(files_needed),
        removed=tuple(removed_urls),
        unresolved=unresolved_urls,
    )
    return text, report


def ensure_vendor_files() -> list[Path]:
    """Bảo đảm mỗi tệp trong VENDOR_LIBS tồn tại trong engines/vendor/.

    Tải về các tệp còn thiếu một lần từ cdn.jsdelivr.net ở phiên bản chuẩn.
    Nếu không có mạng, báo lỗi rõ ràng thay vì tạo tệp giả.
    """
    vendor_dir = _vendor_dir()
    vendor_dir.mkdir(parents=True, exist_ok=True)
    result_paths: list[Path] = []

    for marker, filename in VENDOR_LIBS.items():
        file_path = vendor_dir / filename
        if not file_path.is_file() or file_path.stat().st_size == 0:
            download_url = VENDOR_DOWNLOAD_URLS.get(filename)
            if not download_url:
                raise RuntimeError(f"HYPERFRAMES_VENDOR_NO_DOWNLOAD_URL:{filename}")
            try:
                req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": "HyperFrames-Vendor/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HYPERFRAMES_VENDOR_DOWNLOAD_FAILED:{filename}:HTTP_{resp.status}")
                    content = resp.read()
                    file_path.write_bytes(content)
            except Exception as exc:
                raise RuntimeError(f"HYPERFRAMES_VENDOR_NETWORK_UNAVAILABLE:{filename}:{exc}") from exc
        if file_path not in result_paths:
            result_paths.append(file_path)

    return result_paths
