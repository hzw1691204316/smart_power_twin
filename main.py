"""后端启动入口。通过main:app导出应用；业务接口在app/modules中实现。

统一读取.env.mysql.local并连接MySQL，不再创建内存demo账号。
运行示例：python -m uvicorn main:app --host 127.0.0.1 --port 8000 --no-proxy-headers。"""

from app.application import create_app

app = create_app()
