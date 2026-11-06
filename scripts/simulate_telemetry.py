"""独立模拟采集客户端：默认只说明计划；--send才登录本机API并写入模拟设备测点。

不直连MySQL、不读.env、不持久化密码/令牌，不在FastAPI启动时运行。Ctrl+C停止循环。
"""

import argparse
import getpass
import json
import math
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener


def validate_api_url(value):
    """只接受明确本机HTTP地址，拒绝远端/嵌入凭据/路径；不让测试凭据传到外部服务。"""
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise argparse.ArgumentTypeError(
            "API地址必须是本机http://127.0.0.1:端口或http://localhost:端口"
        )
    return value.rstrip("/")


def api_request(base, path, token="", body=None):
    """调用本机API，禁用环境代理和重定向；错误仅保留业务说明，不输出凭据/原响应。"""
    from urllib.request import HTTPRedirectHandler

    class NoRedirect(HTTPRedirectHandler):
        """登录及采集请求不跟随重定向，避免凭据随错误配置发往其他地址。"""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(
            Request(base + path, data=data, headers=headers), timeout=10
        ) as response:
            return json.load(response)
    except HTTPError as error:
        message = "接口拒绝请求"
        try:
            message = json.load(error).get("error", {}).get("message", message)
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"HTTP {error.code}：{message}") from None
    except (URLError, TimeoutError, ValueError):
        raise RuntimeError("本机后端连接失败或响应异常，请检查启动状态") from None


def page_all(base, path, token):
    """按API分页读取授权台账，不假设数字ID或只读取第一页。"""
    rows = []
    for page in range(1, 10001):
        result = api_request(base, f"{path}?page={page}&pageSize=100", token)
        rows.extend(result["data"])
        if not result["meta"]["hasNext"]:
            return rows
    raise RuntimeError("台账分页过多，请缩小测试范围")


def make_sample(point, device_code, step, now, sequence):
    """给已知测点生成值；step为周期序号，now为带时区时刻，sequence重传保持不变。

    未知测点不编造数据；数值、布尔、文本分别处理，累计量只作确定性递增模拟。
    """
    code = point["code"]
    numeric, text = None, None
    if code == "operation_state" and point["valueType"] == "TEXT":
        text = "模拟并网运行"
    elif code == "online" and point["valueType"] == "BOOLEAN":
        numeric = 1
    elif point["valueType"] == "NUMERIC":
        if code == "active_power":
            hour = (now.hour + 8) % 24 + now.minute / 60
            if device_code == "PV_01":
                numeric = round(100 * max(0, math.sin((hour - 6) * math.pi / 12)), 2)
            elif device_code == "ESS_01":
                numeric = round(45 * math.sin(step / 4), 2)
            else:
                numeric = round(
                    (180 if device_code == "TRANSFORMER_01" else 45) + 10 * math.sin(step / 4), 2
                )
        elif code == "soc":
            numeric = round(65 + 5 * math.sin(step / 4), 2)
        elif code == "temperature":
            numeric = round(36 + 3 * math.sin(step / 4), 2)
        elif code == "voltage":
            numeric = round(380 + 3 * math.sin(step / 4), 2)
        elif code == "total_energy":
            numeric = round(point.get("_counterBase", 10000) + (step + 1) * 0.25, 3)
        else:
            return None
    else:
        return None
    return {
        "pointId": point["id"],
        "sampledAt": now.isoformat(timespec="milliseconds"),
        "sourceSequence": str(sequence),
        "valueNumeric": numeric,
        "valueText": text,
        "quality": "GOOD",
    }


def main():
    """默认只输出计划；显式--send后才提示网页登录凭据，按cycles/interval执行，0周期数表示持续。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", type=validate_api_url, default="http://127.0.0.1:8000")
    parser.add_argument(
        "--site-code", default="HEBI_CHAOGE_SERVICE_DEMO", help="一个已授权模拟站点业务code"
    )
    parser.add_argument(
        "--username", default="sim_operator", help="网页登录账号，不是MySQL连接账号"
    )
    parser.add_argument("--cycles", type=int, default=1, help="次数，默认1；0持续直到Ctrl+C")
    parser.add_argument(
        "--interval", type=float, default=15, help="连续采集间隔秒，至少1；不改数据库测点配置"
    )
    parser.add_argument("--scenario", choices=["normal", "hot", "bad"], default="normal")
    parser.add_argument(
        "--send", action="store_true", help="显式同意本次脚本通过业务API写入模拟数据"
    )
    args = parser.parse_args()
    if args.cycles < 0 or not math.isfinite(args.interval) or args.interval < 1:
        parser.error("cycles须非负，interval须至少1秒")
    if not args.send:
        print(
            f"未发送：计划为{args.site_code}生成{args.scenario}模拟采样。加--send后才登录并提交。"
        )
        return
    password = getpass.getpass("网页账号密码（不显示、不保存）：")
    auth = api_request(
        args.api_url, "/api/v1/auth/login", body={"username": args.username, "password": password}
    )["data"]
    del password
    token = auth["accessToken"]
    if (
        "telemetry:write" not in auth["user"]["permissions"]
        or "monitor:read" not in auth["user"]["permissions"]
    ):
        raise RuntimeError("账号需要monitor:read和telemetry:write权限")
    site = next(
        (s for s in page_all(args.api_url, "/api/v1/sites", token) if s["code"] == args.site_code),
        None,
    )
    if not site or not site["isDemo"]:
        raise RuntimeError("站点不存在、未授权或不是模拟站点，拒绝采样")
    devices = page_all(args.api_url, f"/api/v1/sites/{site['id']}/devices", token)
    points = []
    for device in devices:
        if not device["isDemo"]:
            continue
        latest = {
            p["pointId"]: p
            for p in api_request(args.api_url, f"/api/v1/devices/{device['id']}/latest", token)[
                "data"
            ]
        }
        for p in api_request(args.api_url, f"/api/v1/devices/{device['id']}/points", token)["data"]:
            if not p["enabled"]:
                continue
            if p["code"] == "total_energy":
                value = latest.get(p["id"], {}).get("valueNumeric")
                p["_counterBase"] = value if value is not None else 10000
            points.append((p, device["code"]))
    if not points:
        raise RuntimeError("没有启用的模拟测点，请先导入数据或创建定义")
    step = 0
    while args.cycles == 0 or step < args.cycles:
        now = datetime.now(timezone.utc)
        sequence = time.time_ns()  # 低于有符号64位上限，字符串传输避免JS舍入。
        samples = []
        for definition, code in points:
            item = make_sample(definition, code, step, now, sequence)
            if item is None:
                continue
            if (
                args.scenario == "hot"
                and code == "CHARGER_01"
                and definition["code"] == "temperature"
            ):
                item["valueNumeric"] = 62.1
            if args.scenario == "bad" and code == "PV_01" and definition["code"] == "active_power":
                item.update(valueNumeric=None, quality="BAD")
            samples.append(item)
        if not samples:
            raise RuntimeError("没有本工具支持的测点，不编造未知指标")
        if len(samples) > 500:
            raise RuntimeError("单站样本超过500条，请缩小范围")
        result = api_request(
            args.api_url,
            "/api/v1/telemetry/batches",
            token,
            {"source": "SIMULATED", "samples": samples},
        )["data"]
        print(
            f"第{step + 1}批：新增{result['inserted']}，重复{result['duplicates']}，最新更新{result['latestUpdated']}；模拟，非现场采集"
        )
        step += 1
        if args.cycles == 0 or step < args.cycles:
            time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("模拟采集已停止")
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
