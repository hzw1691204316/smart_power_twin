"""测点查询仓储：按设备／测点读取定义、最新值和有界历史，不提交业务事务。"""

from sqlalchemy import select

from app.modules.monitoring.models import DevicePoint, PointHistory, PointLatest


def device_points(session, device_id):
    """device_id为已授权设备整数ID；返回稳定排序测点定义。"""
    return session.scalars(
        select(DevicePoint).where(DevicePoint.device_id == device_id).order_by(DevicePoint.id)
    ).all()


def latest_values(session, ids):
    """批量读取测点ids最新值；返回{point_id: ORM最新值}，未采集点不补造记录。"""
    return {
        row.point_id: row
        for row in session.scalars(select(PointLatest).where(PointLatest.point_id.in_(ids)))
    }


def history_rows(session, point_id, start, end, limit):
    """UTC时间[start,end)内按时间／序号升序取limit+1条，用于识别截断，不无限加载历史。"""
    return session.scalars(
        select(PointHistory)
        .where(
            PointHistory.point_id == point_id,
            PointHistory.sampled_at >= start,
            PointHistory.sampled_at < end,
        )
        .order_by(PointHistory.sampled_at, PointHistory.source_sequence)
        .limit(limit + 1)
    ).all()
