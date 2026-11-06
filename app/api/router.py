"""接口汇总模块：统一/api/v1前缀，启用台账、账号权限、电力监测、三维绑定、告警和大屏统计。

未来新模块在此注册，不把所有业务处理塞回main.py。"""

from fastapi import APIRouter

from app.modules.alarms.router import router as alarms_router
from app.modules.assets.router import router as assets_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.system.router import router as system_router
from app.modules.twin.router import router as twin_router

router = APIRouter(prefix="/api/v1")
router.include_router(assets_router)
router.include_router(system_router)
router.include_router(monitoring_router)
router.include_router(twin_router)
router.include_router(alarms_router)
router.include_router(dashboard_router)
