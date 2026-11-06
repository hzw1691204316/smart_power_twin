<#
.SYNOPSIS
启动智慧电力后端，仅监听本机，并在启动前检查端口。
.DESCRIPTION
使用项目根目录.venv中的Python运行main:app；不自动安装依赖、不修改MySQL。
端口被占用或受系统限制时给出提示，不自动结束其他进程。
.PARAMETER Port
后端HTTP端口，默认8000，范围1—65535；不是MySQL的3306端口。
.EXAMPLE
& .\scripts\start_backend.ps1 -Port 8001
启动后访问http://127.0.0.1:8001/docs；用Ctrl+C正常停止。
#>
param([ValidateRange(1, 65535)][int]$Port = 8000)

# 以脚本所在位置定位项目，不要求用户事先切换到固定工作目录。
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
$taskPythonPath = Join-Path $taskProjectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPythonPath)) {
    throw 'Missing .venv/Scripts/python.exe. Create the project Python environment first.'
}
# 只临时独占绑定做检测，随后立即释放；真实启动仍可能遇到其他程序抢占端口。
$taskProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
try {
    $taskProbe.Server.ExclusiveAddressUse = $true
    $taskProbe.Start()
}
catch [System.Net.Sockets.SocketException] {
    $taskSocketCode = $_.Exception.NativeErrorCode
    throw "Port $Port is unavailable (Windows socket error $taskSocketCode). Stop the existing backend in its terminal/PyCharm, or use -Port 8001. No existing process was stopped."
}
finally {
    $taskProbe.Stop()
}
Push-Location -LiteralPath $taskProjectRoot
try {
    # 禁止代理头重写客户端IP，配合当前后端的本机访问检查。
    & $taskPythonPath -m uvicorn main:app --host 127.0.0.1 --port $Port --no-proxy-headers
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
