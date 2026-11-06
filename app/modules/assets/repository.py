"""台账查询仓储：只生成和执行SELECT，不提交事务，不决定账号授权。

所有用户值通过SQLAlchemy参数绑定；分页顺序稳定，路线筛选用EXISTS避免关联重复。"""

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from app.modules.assets.models import Device, HighwayRoute, Site, SiteArea, SiteRouteLink


def page_rows(session: Session, statement, page: int, page_size: int):
    """对查询statement计数并分页。

    参数：session为当前请求会话；statement是已加筛选／排序的SELECT；page从1开始，page_size为容量。
    返回：(当前页ORM记录列表, 筛选总数)；越界页为空，总数仍保留。"""
    total = (
        session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    )
    rows = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


class AssetRepository:
    """以请求级session执行台账查询；返回ORM对象，由service转换接口字段。"""

    def __init__(self, session: Session, site_ids=None):
        """参数session为调用方提供的SQLAlchemy Session；仓储不负责关闭或提交它。"""
        self.session = session
        self.site_ids = site_ids

    def get_site(self, site_id: int):
        # SQLite演示库仅支持有符号64位；合法MySQL大ID在演示库中视为不存在。
        """参数site_id为已校验的正整数主键；返回Site或None。

        SQLite无法表示的合法MySQL无符号大ID视为演示库中不存在，不冒出绑定溢出错误。"""
        if self.session.get_bind().dialect.name == "sqlite" and site_id > 9223372036854775807:
            return None
        if self.site_ids is not None and site_id not in self.site_ids:
            return None
        return self.session.get(Site, site_id)

    def alias_match(self, token: str):
        """构造别名搜索条件，不执行查询。token为单个关键词，返回SQL布尔表达式。

        MySQL用JSON_SEARCH，SQLite用json_each解码数组值，避免中文JSON转义导致漏查；%和_按字面转义。"""
        if self.session.get_bind().dialect.name == "mysql":
            escaped = token.lower().replace("/", "//").replace("%", "/%").replace("_", "/_")
            # 由JSON函数搜索解码后的数组值，避免把JSON转义或分隔符当作别名。
            return func.json_search(
                func.lower(cast(Site.aliases_json, String)), "one", "%" + escaped + "%", "/"
            ).is_not(None)
        aliases = func.json_each(Site.aliases_json).table_valued("value")
        return exists(
            select(1).select_from(aliases).where(aliases.c.value.icontains(token, autoescape=True))
        ).correlate(Site)

    def sites(
        self,
        page: int,
        page_size: int,
        q: str,
        site_type,
        scale,
        province_code,
        city_name,
        highway,
        status,
    ):
        """分页查询站点。

        参数：page/page_size控制分页；q为空格分词，所有词均须命中名称、编码、城市、别名或路线之一；
        site_type为TOLL/SERVICE，scale为S/M/L，province_code为标准六位省码，city_name为城市名，
        highway为完整G/S编号，status为站点生命周期；None条件不参与过滤。
        返回：(Site列表, 总数)。省码兼容数据库两位／六位；城市兼容带市后缀；路线精确匹配并去重。"""
        statement = select(Site)
        if self.site_ids is not None:
            statement = statement.where(Site.id.in_(self.site_ids))
        if site_type:
            statement = statement.where(Site.site_type == site_type)
        if scale:
            statement = statement.where(Site.scale_level == scale)
        if province_code:
            statement = statement.where(Site.province_code.in_([province_code, province_code[:2]]))
        if city_name:
            city = city_name.strip().removesuffix("市")
            statement = statement.where(Site.city_name.in_([city, city + "市"]))
        if status:
            statement = statement.where(Site.status == status)
        if highway:
            statement = statement.where(
                exists().where(
                    SiteRouteLink.site_id == Site.id,
                    SiteRouteLink.route_id == HighwayRoute.id,
                    HighwayRoute.route_code == highway.strip().upper(),
                )
            )
        # 每个空格关键词均须命中某个字段；参数绑定与LIKE转义避免通配符误查。
        for token in q.split():
            route_match = exists().where(
                SiteRouteLink.site_id == Site.id,
                SiteRouteLink.route_id == HighwayRoute.id,
                or_(
                    HighwayRoute.route_code.icontains(token, autoescape=True),
                    HighwayRoute.name.icontains(token, autoescape=True),
                ),
            )
            statement = statement.where(
                or_(
                    Site.name.icontains(token, autoescape=True),
                    Site.code.icontains(token, autoescape=True),
                    Site.city_name.icontains(token, autoescape=True),
                    self.alias_match(token),
                    route_match,
                )
            )
        return page_rows(self.session, statement.order_by(Site.code, Site.id), page, page_size)

    def routes_for_sites(self, ids: list[int]):
        """批量读取ids中的站点路线，避免逐站查询。

        ids为整数站点ID列表；返回{站点ID: [(关联对象, 路线对象), ...]}，无关联的站点不出现在字典中。"""
        if not ids:
            return {}
        rows = self.session.execute(
            select(SiteRouteLink, HighwayRoute)
            .join(HighwayRoute, SiteRouteLink.route_id == HighwayRoute.id)
            .where(SiteRouteLink.site_id.in_(ids))
            .order_by(SiteRouteLink.is_primary.desc(), HighwayRoute.route_code, SiteRouteLink.id)
        ).all()
        grouped = {}
        for link, route in rows:
            grouped.setdefault(link.site_id, []).append((link, route))
        return grouped

    def devices(self, site_id: int, page: int, page_size: int, system_type, status, q: str):
        """只查询site_id所属设备。page/page_size控制分页，system_type为能源系统，
        status为设备资产状态，q按设备名称／编码组合检索。返回：(Device列表, 总数)。"""
        statement = select(Device).where(Device.site_id == site_id)
        if system_type:
            statement = statement.where(Device.system_type == system_type)
        if status:
            statement = statement.where(Device.status == status)
        for token in q.split():
            statement = statement.where(
                or_(
                    Device.name.icontains(token, autoescape=True),
                    Device.code.icontains(token, autoescape=True),
                )
            )
        return page_rows(self.session, statement.order_by(Device.code, Device.id), page, page_size)

    def device(self, site_id: int, device_id: int):
        """用site_id和device_id两个整数共同限定查询，返回Device或None。

        即使设备存在，只要属于其他站点也视为不存在；不是仅按设备ID读取。"""
        if self.session.get_bind().dialect.name == "sqlite" and device_id > 9223372036854775807:
            return None
        return self.session.scalar(
            select(Device).where(Device.site_id == site_id, Device.id == device_id)
        )

    def areas(self, site_id: int):
        """参数site_id为所属站点整数ID；返回按编码、ID排序的区域平铺列表，可为空。"""
        return self.session.scalars(
            select(SiteArea).where(SiteArea.site_id == site_id).order_by(SiteArea.code, SiteArea.id)
        ).all()

    def highways(self, page: int, page_size: int, q: str):
        """参数page/page_size为分页，q按路线名称／编号分词搜索；返回(路线列表, 总数)。

        查询的是业务台账，不是前端全省公开路网几何。"""
        statement = select(HighwayRoute)
        if self.site_ids is not None:
            statement = statement.where(
                exists().where(
                    SiteRouteLink.route_id == HighwayRoute.id,
                    SiteRouteLink.site_id.in_(self.site_ids),
                )
            )
        for token in q.split():
            statement = statement.where(
                or_(
                    HighwayRoute.route_code.icontains(token, autoescape=True),
                    HighwayRoute.name.icontains(token, autoescape=True),
                )
            )
        return page_rows(
            self.session,
            statement.order_by(HighwayRoute.route_code, HighwayRoute.id),
            page,
            page_size,
        )
