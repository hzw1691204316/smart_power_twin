"""按业务组织的模块。"""


def register_models():
    """注册账号、台账、监测、三维和告警共19张表；大屏汇总尚未启用。"""
    from app.modules.alarms import models as alarms
    from app.modules.assets import models as assets
    from app.modules.monitoring import models as monitoring
    from app.modules.system import models as system
    from app.modules.twin import models as twin

    return assets, system, monitoring, twin, alarms
