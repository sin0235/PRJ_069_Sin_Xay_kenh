<#
.SYNOPSIS
  Khởi động toàn bộ hệ thống dev local chỉ bằng một lệnh, kiểm tra từng thành phần rồi báo kết quả.

.DESCRIPTION
  Chạy lần lượt: 9Router (LLM) -> API, worker, web, gateway, tunnel (qua khoi_dong_local.ps1) -> chờ /readyz -> kiểm tra
  cấu hình LLM, tunnel, hồ sơ Flow -> mở trình duyệt đúng địa chỉ đăng nhập. Chạy lại bao nhiêu lần cũng được:
  thành phần nào đang chạy thì giữ nguyên.

.PARAMETER Dung
  Dừng API, worker, web, gateway, tunnel của dự án (không dừng 9Router vì có thể dùng chung).

.PARAMETER SuaLLM
  Nếu cấu hình LLM trong CSDL không trỏ tới 9Router local thì đổi lại thành http://127.0.0.1:20128/v1 (có ghi audit).

.PARAMETER CapNhatGiaoDien
  Build lại giao diện trên GitHub Actions (build_web_local.yaml), tải bản mới về runtime\web (giữ bản cũ để quay lại) rồi khởi động lại web.
  Dùng khi đã sửa mã trong sin_creator_os và đã đẩy lên nhánh. Máy chỉ có 8 GB RAM nên việc build chạy trên Actions chứ không chạy local.

.PARAMETER RunId
  Dùng một lượt build đã chạy xong (mã run trên GitHub) thay vì tạo lượt build mới; chỉ có tác dụng cùng -CapNhatGiaoDien.

.PARAMETER KhongMoTrinhDuyet
  Không tự mở trình duyệt ở cuối.

.EXAMPLE
  .\chay_he_thong.ps1
  .\chay_he_thong.ps1 -SuaLLM
  .\chay_he_thong.ps1 -Dung
#>
param(
    [switch]$Dung,
    [switch]$SuaLLM,
    [switch]$CapNhatGiaoDien,
    [string]$RunId = '',
    [switch]$KhongMoTrinhDuyet,
    [int]$ChoToiDaGiay = 150
)
$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = 'utf-8'
$thuMuc = $PSScriptRoot
$khoiDong = Join-Path $thuMuc 'khoi_dong_local.ps1'
$ketQua = New-Object System.Collections.Generic.List[object]

function Ghi([string]$trangThai, [string]$muc, [string]$chiTiet) {
    $ketQua.Add([pscustomobject]@{ TrangThai = $trangThai; Muc = $muc; ChiTiet = $chiTiet })
    $mau = @{ 'OK' = 'Green'; 'CANH BAO' = 'Yellow'; 'LOI' = 'Red' }[$trangThai]
    Write-Host ('[{0,-8}] {1,-22} {2}' -f $trangThai, $muc, $chiTiet) -ForegroundColor $mau
}

function CongDangNghe([int]$cong) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $cong -ErrorAction SilentlyContinue)
}

function MaHttp([string]$url, [int]$giay = 15) {
    try { return [int](Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec $giay -MaximumRedirection 0 -ErrorAction Stop).StatusCode }
    catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

function LayReadyz {
    try { return (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8001/readyz' -TimeoutSec 8).Content | ConvertFrom-Json }
    catch { return $null }
}

# ----- Dừng -----
if ($Dung) {
    foreach ($ten in 'worker', 'web', 'gateway', 'tunnel', 'api') {
        $tep = Join-Path $thuMuc "$ten.pid"
        if (-not (Test-Path -LiteralPath $tep)) { Write-Host "${ten}: không có tệp PID"; continue }
        $ma = [int](Get-Content -LiteralPath $tep)
        $tt = Get-CimInstance Win32_Process -Filter "ProcessId=$ma" -ErrorAction SilentlyContinue
        if ($tt -and $tt.CommandLine -and $tt.CommandLine.Contains($thuMuc)) {
            Stop-Process -Id $ma -Force -ErrorAction SilentlyContinue
            Write-Host "${ten}: đã dừng ($ma)"
        } else { Write-Host "${ten}: không còn chạy" }
        Remove-Item -LiteralPath $tep -Force -ErrorAction SilentlyContinue
    }
    Write-Host '9Router giữ nguyên (không dừng). Xong.'
    return
}

Write-Host '=== Khởi động hệ thống PRJ_069 (dev local) ===' -ForegroundColor Cyan

# ----- 1. Điều kiện cần có -----
if (-not (Test-Path -LiteralPath (Join-Path $thuMuc '.env.dev'))) { Ghi 'LOI' 'Cấu hình' 'Thiếu .env.dev; không tự tạo.'; return }
foreach ($lenh in 'python', 'node', 'cloudflared') {
    if (Get-Command $lenh -ErrorAction SilentlyContinue) { continue }
    Ghi 'LOI' "Công cụ $lenh" 'Không tìm thấy trong PATH.'
}
if (-not (Test-Path -LiteralPath (Join-Path $thuMuc '.env.tunnel_token'))) { Ghi 'LOI' 'Tunnel' 'Thiếu .env.tunnel_token.' }
if (-not (Test-Path -LiteralPath (Join-Path $thuMuc 'runtime/web/server.js'))) { Ghi 'LOI' 'Giao diện' 'Chưa có bản FE (runtime/web/server.js) do GitHub Actions build.' }
if ($ketQua | Where-Object { $_.TrangThai -eq 'LOI' }) { Write-Host 'Dừng vì thiếu điều kiện cần có.' -ForegroundColor Red; return }

# ----- 2. 9Router (LLM) -----
if (-not (CongDangNghe 20128)) {
    $lenh9 = Get-Command 9router -ErrorAction SilentlyContinue
    if ($lenh9) {
        $cli = Join-Path (Split-Path $lenh9.Source) 'node_modules\9router\cli.js'
        if (Test-Path -LiteralPath $cli) {
            Start-Process -FilePath (Get-Command node).Source -ArgumentList ('"{0}" -n --skip-update' -f $cli) -WindowStyle Hidden | Out-Null
            for ($i = 0; $i -lt 40 -and -not (CongDangNghe 20128); $i++) { Start-Sleep -Seconds 1 }
        }
    }
}
$ma9 = MaHttp 'http://127.0.0.1:20128/v1/models'
if ($ma9 -ge 200 -and $ma9 -lt 500 -and $ma9 -ne 0) { Ghi 'OK' '9Router (LLM)' "cổng 20128 phản hồi (HTTP $ma9)" }
else { Ghi 'LOI' '9Router (LLM)' 'Không chạy được 9Router ở cổng 20128. Mở 9Router thủ công rồi chạy lại.' }


# ----- 2b. Cập nhật giao diện (tùy chọn): build trên Actions, tải về, thay runtime\web -----
if ($CapNhatGiaoDien) {
    $kho = 'sin0235/PRJ_069_Sin_Xay_kenh'
    $dongRef = Select-String -Path (Join-Path $thuMuc '.env.dev') -Pattern '^REMOTE_GITHUB_REF=' | Select-Object -First 1
    $nhanh = if ($dongRef) { ($dongRef.Line -replace '^REMOTE_GITHUB_REF=', '').Trim('"', "'", ' ') } else { 'dev/local-remote-video-tests' }
    try {
        if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Không tìm thấy lệnh gh (GitHub CLI).' }
        if (-not $RunId) {
            Write-Host "... gửi build giao diện lên GitHub Actions (nhánh $nhanh)" -ForegroundColor DarkGray
            & gh workflow run build_web_local.yaml --repo $kho --ref $nhanh | Out-Null
            Start-Sleep -Seconds 10
            $RunId = (& gh run list --repo $kho --workflow build_web_local.yaml --limit 1 --json databaseId --jq '.[0].databaseId') | Select-Object -First 1
        }
        Write-Host "... chờ build giao diện (run $RunId): https://github.com/$kho/actions/runs/$RunId" -ForegroundColor DarkGray
        $ketThuc = $null
        for ($i = 0; $i -lt 180; $i++) {
            $trangThai = (& gh run view $RunId --repo $kho --json status,conclusion) -join '' | ConvertFrom-Json
            $tt = "$($trangThai.status) $($trangThai.conclusion)"
            if ($tt -like 'completed*') { $ketThuc = $tt; break }
            Start-Sleep -Seconds 15
        }
        if (-not $ketThuc -or $ketThuc -notlike 'completed success*') { throw "Build giao diện không đạt ($ketThuc). Xem log: gh run view $RunId --repo $kho --log-failed" }
        $nhan = Get-Date -Format 'yyyyMMdd_HHmmss'
        $moi = Join-Path $thuMuc "runtime\web_phat_hanh_$nhan"
        & gh run download $RunId --repo $kho -n giao_dien_windows -D $moi
        foreach ($can in 'server.js', '.next\static', 'public') {
            if (-not (Test-Path -LiteralPath (Join-Path $moi $can))) { throw "Bản tải về thiếu $can; không thay runtime\web." }
        }
        # Dừng web đang chạy (chỉ tiến trình của dự án), giữ bản cũ để quay lại rồi thay bản mới.
        $tepWeb = Join-Path $thuMuc 'web.pid'
        if (Test-Path -LiteralPath $tepWeb) {
            $maWeb = [int](Get-Content -LiteralPath $tepWeb)
            $ttWeb = Get-CimInstance Win32_Process -Filter "ProcessId=$maWeb" -ErrorAction SilentlyContinue
            if ($ttWeb -and $ttWeb.CommandLine -and $ttWeb.CommandLine.Contains($thuMuc)) { Stop-Process -Id $maWeb -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 }
            Remove-Item -LiteralPath $tepWeb -Force -ErrorAction SilentlyContinue
        }
        $web = Join-Path $thuMuc 'runtime\web'
        if (Test-Path -LiteralPath $web) { Rename-Item -LiteralPath $web -NewName "web_cu_$nhan" }
        Rename-Item -LiteralPath $moi -NewName 'web'
        Ghi 'OK' 'Giao diện (build mới)' "run $RunId đã thay runtime\web; bản cũ giữ ở runtime\web_cu_$nhan"
    }
    catch { Ghi 'LOI' 'Giao diện (build mới)' $_.Exception.Message }
}

# ----- 3. API, worker, web, gateway, tunnel -----
Write-Host '... khởi động API, worker, web, gateway, tunnel' -ForegroundColor DarkGray
try { & $khoiDong -ThanhPhan all 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray } }
catch { Ghi 'LOI' 'Khởi động' $_.Exception.Message }

# ----- 4. Chờ API và worker sẵn sàng -----
$readyz = $null
$batDau = Get-Date
while (((Get-Date) - $batDau).TotalSeconds -lt $ChoToiDaGiay) {
    $readyz = LayReadyz
    if ($readyz -and $readyz.components.database.state -eq 'READY' -and $readyz.components.worker.state -eq 'READY') { break }
    Start-Sleep -Seconds 3
}
if (-not $readyz) { Ghi 'LOI' 'API (8001)' 'Không trả lời /readyz. Xem ha_tang\chay_dev_local\api_error.log.' }
else {
    Ghi $(if ($readyz.components.database.state -eq 'READY') { 'OK' } else { 'LOI' }) 'Cơ sở dữ liệu' $readyz.components.database.state
    Ghi $(if ($readyz.components.worker.state -eq 'READY') { 'OK' } else { 'LOI' }) 'Worker' $(if ($readyz.components.worker.state -eq 'READY') { 'READY (xử lý lập kế hoạch storyboard và lượt chạy)' } else { 'chưa sẵn sàng: ' + $readyz.components.worker.error_code })
    $tts = $readyz.components.tts
    Ghi $(if ($tts.state -eq 'READY') { 'OK' } else { 'CANH BAO' }) 'Giọng đọc (TTS)' $(if ($tts.state -eq 'READY') { "READY ($($tts.mode))" } else { "$($tts.state) $($tts.error_code)" })
}
foreach ($c in @(@{ T = 'Giao diện (3000)'; P = 3000 }, @{ T = 'Gateway (13069)'; P = 13069 }, @{ T = 'Worker (8090)'; P = 8090 })) {
    Ghi $(if (CongDangNghe $c.P) { 'OK' } else { 'LOI' }) $c.T $(if (CongDangNghe $c.P) { 'đang nghe' } else { 'không nghe; xem tệp *_error.log cùng thư mục' })
}

# ----- 5. Cấu hình LLM và hồ sơ Flow -----
$thamSo = @((Join-Path $thuMuc 'kiem_tra_cau_hinh.py'))
if ($SuaLLM) { $thamSo += '--sua-llm' }
$dong = & python @thamSo 2>$null | Select-Object -Last 1
$cauHinh = $null
try { $cauHinh = $dong | ConvertFrom-Json } catch {}
if (-not $cauHinh -or $cauHinh.loi) { Ghi 'CANH BAO' 'Cấu hình LLM/Flow' "không đọc được cấu hình ($($cauHinh.loi))" }
else {
    $maLLM = $cauHinh.llm.host
    if ($maLLM -match '^(127\.0\.0\.1|localhost):20128$') { Ghi 'OK' 'Địa chỉ LLM' "9Router local ($maLLM)" }
    else { Ghi 'CANH BAO' 'Địa chỉ LLM' "đang trỏ tới $maLLM, không phải 9Router local; tạo storyboard sẽ lỗi nếu nơi đó không chạy. Chạy lại với -SuaLLM để đổi." }
    if (-not $cauHinh.llm.enabled) { Ghi 'CANH BAO' 'LLM' 'đang tắt (is_enabled=false)' }
    switch ($cauHinh.flow_google_cookie) {
        $true { Ghi 'OK' 'Flow (đăng nhập)' 'hồ sơ Flow có cookie đăng nhập Google' }
        $false { Ghi 'CANH BAO' 'Flow (đăng nhập)' 'hồ sơ Flow CHƯA có cookie đăng nhập Google; cần đăng nhập lại (chạy runtime\mo_dang_nhap_flow.py)' }
        default { Ghi 'CANH BAO' 'Flow (đăng nhập)' 'không đọc được (trình duyệt đang giữ hồ sơ Flow); đóng cửa sổ Edge của hồ sơ này rồi chạy lại' }
    }
}

# ----- 6. Tunnel và địa chỉ đăng nhập -----
$dongOrigin = Select-String -Path (Join-Path $thuMuc '.env.dev') -Pattern '^AUTH_ALLOWED_ORIGINS=' | Select-Object -First 1
$diaChi = if ($dongOrigin) { ($dongOrigin.Line -replace '^AUTH_ALLOWED_ORIGINS=', '').Trim('"', "'", ' ').Split(',')[0] } else { $null }
if ($diaChi) {
    $maTunnel = MaHttp $diaChi
    if ($maTunnel -ge 200 -and $maTunnel -lt 500) { Ghi 'OK' 'Tunnel / địa chỉ web' "$diaChi phản hồi (HTTP $maTunnel)" }
    else { Ghi 'LOI' 'Tunnel / địa chỉ web' "$diaChi không truy cập được (HTTP $maTunnel); kiểm tra tunnel.log" }
} else { Ghi 'CANH BAO' 'Tunnel / địa chỉ web' 'không đọc được AUTH_ALLOWED_ORIGINS trong .env.dev' }

# ----- Tổng kết -----
$loi = @($ketQua | Where-Object { $_.TrangThai -eq 'LOI' }).Count
$canhBao = @($ketQua | Where-Object { $_.TrangThai -eq 'CANH BAO' }).Count
Write-Host ''
if ($loi) { Write-Host "Có $loi lỗi và $canhBao cảnh báo. Sửa lỗi theo chi tiết ở trên rồi chạy lại." -ForegroundColor Red }
else { Write-Host "Hệ thống sẵn sàng ($canhBao cảnh báo)." -ForegroundColor Green }
if ($diaChi) {
    Write-Host "Đăng nhập tại: $diaChi   (KHÔNG dùng localhost hay 127.0.0.1: sẽ báo 'Origin không hợp lệ')" -ForegroundColor Cyan
    if (-not $KhongMoTrinhDuyet -and -not $loi) { Start-Process $diaChi }
}
Write-Host 'Dừng hệ thống: .\chay_he_thong.ps1 -Dung' -ForegroundColor DarkGray
