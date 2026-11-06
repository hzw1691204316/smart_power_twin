# 后端启动端口冲突与跨域说明

日期：2026-10-14。

## 本次结论

用户启动日志中的WinError 10013出现在服务器绑定监听端口时，尚未处理浏览器请求，因此不是前后端跨域造成的。

现场检查发现127.0.0.1:8000已由上一轮Codex启动的测试服务占用：监听进程29412，父进程16168，与前轮记录及启动命令一致。另一次独占端口预检返回10048。已仅停止确认属于本轮项目的旧测试服务，没有停止用户的其他程序。

Windows IPv4、IPv6 TCP排除端口列表均未显示保留范围。释放端口后，实际运行同项目uvicorn的--reload模式成功；健康、站点查询及跨域预检均正常。验证服务已用Ctrl+C正常关闭，8000留给用户启动。

## 你现在怎么运行

在PyCharm重新点运行即可；确保主机127.0.0.1、端口8000、应用main:app，使用项目.venv解释器。不要同时在PyCharm和终端启动两份。

也可以在根目录终端启动：

```powershell
cd D:\study_software\PythonProject\smart_power_twin
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

看到Application startup complete、Uvicorn running后，打开 http://127.0.0.1:8000/docs 。

## 启动脚本的完善

`scripts/start_backend.ps1` 新增127.0.0.1独占绑定预检。端口不可用时，在启动uvicorn之前明确提示端口号、Windows套接字错误码、停止已有后端或改用8001的处理方式；不会自动杀进程或修改系统设置。

若今后再次冲突，先在已运行的PyCharm／终端停止原实例；其他软件占用时，可选择8001并同步修改访问地址。无需因为本次问题修改MySQL、关闭防火墙或提升权限。

## CORS检查结果

现有配置允许 http://localhost:5173 和 http://127.0.0.1:5173 发起GET查询。已新增自动检查：

- 两个Origin的GET均带正确Access-Control-Allow-Origin。
- 两个Origin的OPTIONS预检允许GET及content-type。
- 不在配置中的Origin不返回允许来源，POST预检不被放行。
- 数据库查询失败时仍返回可被前端读取的503和正确CORS头，避免将业务错误误判为跨域。

实际热重载服务上也验证了GET和OPTIONS，均为200且允许来源正确。当前前端本身未接后端业务数据，本轮也没有改前端。

## 验证与续接

43项pytest通过，Ruff代码与格式检查通过；原台账功能继续保留。默认仍为明确标注的进程内演示数据，没有连接或修改MySQL。后续用户测试请按桌面C后端第一模块_站点与设备台账_测试指南.md进行。
