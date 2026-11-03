param(
    [ValidateSet('all','api','web','gateway','tunnel','worker')]
    [string]$ThanhPhan = 'all'
)
$ErrorActionPreference = 'Stop'
$thuMuc = $PSScriptRoot
$goc = (Resolve-Path (Join-Path $thuMuc '../..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $thuMuc '.env.dev'))) {
    throw 'Thiếu cấu hình .env.dev. Không tự khởi tạo DB hoặc tài khoản thay thế.'
}

function KhoiDong($ten, $chuongTrinh, $thamSo, $noiChay) {
    $tepPid = Join-Path $thuMuc "$ten.pid"
    if (Test-Path -LiteralPath $tepPid) {
        $maTienTrinh = [int](Get-Content -LiteralPath $tepPid)
        $tienTrinh = Get-CimInstance Win32_Process -Filter "ProcessId=$maTienTrinh"
        if ($tienTrinh) {
            if ($tienTrinh.CommandLine -and $tienTrinh.CommandLine.Contains($thuMuc)) {
                Write-Output "$ten đã chạy: $maTienTrinh"
                return
            }
            throw "PID của $ten đã được tiến trình khác dùng. Kiểm tra tệp PID trước khi tiếp tục."
        }
    }
    $tienTrinh = Start-Process -FilePath $chuongTrinh -ArgumentList $thamSo -WorkingDirectory $noiChay -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $thuMuc "$ten.log") -RedirectStandardError (Join-Path $thuMuc "${ten}_error.log") -PassThru
    Set-Content -LiteralPath $tepPid -Value $tienTrinh.Id
    Write-Output "$ten đã khởi động: $($tienTrinh.Id)"
}

$env:PYTHONIOENCODING = 'utf-8'
$env:GOMEMLIMIT = '128MiB'
if ($ThanhPhan -in @('all','api')) {
    KhoiDong 'api' (Get-Command python).Source ('"{0}" api' -f (Join-Path $thuMuc 'chay_thanh_phan.py')) $goc
}
if ($ThanhPhan -in @('all','web')) {
    $server = Join-Path $thuMuc 'runtime/web/server.js'
    if (-not (Test-Path -LiteralPath $server)) { throw 'Chưa có bản FE do GitHub Actions build.' }
    $env:NODE_ENV = 'production'
    $env:NODE_OPTIONS = '--max-old-space-size=384'
    $env:HOSTNAME = '127.0.0.1'
    $env:PORT = '3000'
    $env:NEXT_TELEMETRY_DISABLED = '1'
    KhoiDong 'web' (Get-Command node).Source ('"{0}"' -f $server) (Split-Path $server)
}
if ($ThanhPhan -in @('all','gateway')) {
    $caddy = Join-Path $thuMuc 'runtime/tools/caddy/caddy.exe'
    if (-not (Test-Path -LiteralPath $caddy)) { throw 'Chưa có Caddy đã đối chiếu checksum.' }
    KhoiDong 'gateway' $caddy ('run --config "{0}" --adapter caddyfile' -f (Join-Path $thuMuc 'caddyfile')) $goc
}
if ($ThanhPhan -in @('all','tunnel')) {
    $tepToken = Join-Path $thuMuc '.env.tunnel_token'
    if (-not (Test-Path -LiteralPath $tepToken)) { throw 'Thiếu tệp token Tunnel đã được bảo vệ.' }
    KhoiDong 'tunnel' (Get-Command cloudflared).Source ('--no-autoupdate tunnel run --token-file "{0}"' -f $tepToken) $goc
}
if ($ThanhPhan -in @('all','worker')) {
    KhoiDong 'worker' (Get-Command python).Source ('"{0}" worker' -f (Join-Path $thuMuc 'chay_thanh_phan.py')) $goc
}
