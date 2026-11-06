"""台账业务服务：校验身份及归属、统一ID／省码、组装响应和来源说明。

不绘制页面、不生成实时读数、不直接拼SQL；所有台账状态与监测状态分开。"""

from app.common.pagination import Page, PageMeta, Result, SourceMeta
from app.core.exceptions import BusinessError
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import AreaOut, DeviceOut, HighwayOut, RouteOut, SiteOut

TEST_NOTICE = "自动化测试样例：公开参考坐标、区域和设备参数并非现场台账或实时监测。"
MYSQL_NOTICE = "来自所配置MySQL的台账；isDemo说明记录是否演示。ACTIVE仅表示资产有效，不代表在线；实时采样另从监测接口查询。"


def numeric_id(value: str) -> int:
    """把路径value字符串转换为数据库整数ID；路由已保证正整数格式。

    返回int；超过MySQL UNSIGNED BIGINT上限时抛出422 BusinessError，避免数据库溢出。"""
    result = int(value)
    if result > 18446744073709551615:
        raise BusinessError("INVALID_ARGUMENT", "ID超出MySQL无符号BIGINT范围", 422)
    return result


def optional_id(value):
    """把可空主键value转换为字符串；None仍返回None，防止产生字符串'None'或丢失大整数精度。"""
    return str(value) if value is not None else None


def optional_number(value):
    """把可空Decimal数值value转换为JSON数字；None仍为空，不能误当0。仅用于本模块坐标／额定参数。"""
    return float(value) if value is not None else None


class AssetService:
    """站点与设备查询的业务入口。repository执行数据库查询，source标识mysql或隔离测试。"""

    def __init__(self, repository: AssetRepository, source: str):
        """参数repository为请求级仓储；source为已校验的数据模式，用于所有成功响应的来源说明。"""
        self.repository = repository
        self.source = source

    def meta(self):
        """返回SourceMeta：明确演示／MySQL来源；使用MySQL也不代表每条记录都是现场资料。"""
        return SourceMeta(
            data_source=self.source, notice=TEST_NOTICE if self.source == "test" else MYSQL_NOTICE
        )

    def result(self, data):
        """参数data为单项对象或普通数组；返回带来源meta的Result，不添加虚构业务数据。"""
        return Result(data=data, meta=self.meta())

    def page(self, rows, total, page, page_size):
        """组装分页响应。rows为已转换的当前页数据，total为筛选总数，page从1开始，page_size为容量。

        返回Page；has_next通过页容量与总数判断，不以当前数组是否为空替代总数。"""
        return Page(
            data=rows,
            meta=PageMeta(
                **self.meta().model_dump(),
                total=total,
                page=page,
                page_size=page_size,
                has_next=page * page_size < total,
            ),
        )

    def require_site(self, site_id: str):
        """参数site_id为路径主键字符串；返回存在的Site。

        主键超界抛422，站点不存在抛404 SITE_NOT_FOUND；用于区分不存在和存在但无设备的站点。"""
        site = self.repository.get_site(numeric_id(site_id))
        if site is None:
            raise BusinessError("SITE_NOT_FOUND", "未找到该站点")
        return site

    def site_out(self, site, routes):
        """把site ORM对象及routes关联二元组列表转换为SiteOut。

        主键字符串化、两位省码扩为六位、保留未知坐标及来源；routes来自已批量查询的数据。"""
        province = site.province_code
        if len(province) == 2 and province.isdigit():
            province += "0000"
        return SiteOut(
            id=str(site.id),
            code=site.code,
            name=site.name,
            site_type=site.site_type,
            scale_level=site.scale_level,
            complex_code=site.complex_code,
            province_code=province,
            city_name=site.city_name,
            longitude=optional_number(site.longitude),
            latitude=optional_number(site.latitude),
            coordinate_system=site.coordinate_system,
            location_source=site.location_source,
            is_demo=bool(site.is_demo),
            asset_status=site.status,
            routes=[self.route_out(link, route) for link, route in routes],
        )

    @staticmethod
    def route_out(link, route):
        """完整路线关系响应；保留关联ID/编码、米制桩号、区域与接入类型，未知桩号不补0。"""
        return RouteOut(
            id=str(link.id),
            site_id=str(link.site_id),
            link_code=link.link_code,
            area_id=optional_id(link.area_id),
            route_id=str(route.id),
            route_code=route.route_code,
            name=route.name,
            direction_code=link.direction_code,
            direction_label=link.direction_label,
            is_primary=bool(link.is_primary),
            chainage_m=optional_number(link.chainage_m),
            access_type=link.access_type,
        )

    def list_sites(self, page, page_size, **filters):
        """参数page/page_size控制分页，filters包含q、site_type、scale、province_code、city_name、highway、status。

        标准化两位省码，批量加载路线；返回Page[SiteOut]。这里只做台账查询，不调用监测模块。"""
        province = filters.get("province_code")
        if province and len(province) == 2:
            filters["province_code"] = province + "0000"
        sites, total = self.repository.sites(page, page_size, **filters)
        routes = self.repository.routes_for_sites([site.id for site in sites])
        return self.page(
            [self.site_out(site, routes.get(site.id, [])) for site in sites], total, page, page_size
        )

    def site_detail(self, site_id):
        """参数site_id为站点ID字符串；返回带路线的Result[SiteOut]。不存在抛404，ID超界抛422。"""
        site = self.require_site(site_id)
        routes = self.repository.routes_for_sites([site.id])
        return self.result(self.site_out(site, routes.get(site.id, [])))

    def device_out(self, device):
        """把device ORM对象转为DeviceOut。主键字符串化，保留空额定参数；asset_status不转成在线状态。"""
        return DeviceOut(
            id=str(device.id),
            site_id=str(device.site_id),
            area_id=optional_id(device.area_id),
            parent_device_id=optional_id(device.parent_device_id),
            code=device.code,
            name=device.name,
            device_type=device.device_type,
            system_type=device.system_type,
            asset_status=device.status,
            rated_power_kw=optional_number(device.rated_power_kw),
            rated_energy_kwh=optional_number(device.rated_energy_kwh),
            rated_capacity_kva=optional_number(device.rated_capacity_kva),
            manufacturer=device.manufacturer,
            model_code=device.model_code,
            is_demo=bool(device.is_demo),
        )

    def list_devices(self, site_id, page, page_size, **filters):
        """参数site_id为站点ID字符串，page/page_size为分页，filters含system_type、status、q。

        先确认站点存在，再返回其设备Page；已有站点无设备返回空列表，不存在站点抛404。"""
        site = self.require_site(site_id)
        devices, total = self.repository.devices(site.id, page, page_size, **filters)
        return self.page([self.device_out(device) for device in devices], total, page, page_size)

    def device_detail(self, site_id, device_id):
        """参数site_id、device_id均为路径字符串；返回Result[DeviceOut]。

        先校验站点，再核对设备归属；跨站或不存在的设备抛404 DEVICE_NOT_FOUND。"""
        site = self.require_site(site_id)
        device = self.repository.device(site.id, numeric_id(device_id))
        if device is None:
            raise BusinessError("DEVICE_NOT_FOUND", "该站点下未找到此设备")
        return self.result(self.device_out(device))

    def list_areas(self, site_id):
        """参数site_id为站点ID字符串；返回带来源的区域平铺列表Result。不存在站点抛404。"""
        site = self.require_site(site_id)
        return self.result(
            [
                AreaOut(
                    id=str(area.id),
                    site_id=str(area.site_id),
                    parent_id=optional_id(area.parent_id),
                    code=area.code,
                    name=area.name,
                    area_type=area.area_type,
                )
                for area in self.repository.areas(site.id)
            ]
        )

    def list_highways(self, page, page_size, q):
        """参数page/page_size为分页，q为名称／编号关键词；返回业务路线Page，不包含全省路网统计。"""
        highways, total = self.repository.highways(page, page_size, q)
        return self.page(
            [
                HighwayOut(
                    id=str(route.id),
                    route_code=route.route_code,
                    name=route.name,
                    status=route.status,
                    geometry_uri=route.geometry_uri,
                    coordinate_system=route.coordinate_system,
                )
                for route in highways
            ],
            total,
            page,
            page_size,
        )
