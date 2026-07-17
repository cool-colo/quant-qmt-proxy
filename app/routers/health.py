"""健康检查路由。

- ``/health/live``  存活检查：进程是否起来（不探测底层依赖），供重启守护判断进程本身。
- ``/health/ready`` 就绪检查：深度探测 xtdata 行情连接与 xttrader 交易可用性，
  在 dev/prod 下依赖未就绪时返回 HTTP 503，供外部脚本轮询后触发再次重启或告警。
- ``/health/``      汇总信息（含深度快照），始终 200，便于人工排查。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Response

from app.config import Settings, get_settings
from app.dependencies import get_trading_session_manager, get_xtdata_gateway
from app.services.trading_session_manager import TradingSessionManager
from app.services.xtdata_gateway import XtDataGateway
from app.utils.helpers import format_response

router = APIRouter(prefix="/health", tags=["健康检查"])


def _build_readiness(
    settings: Settings,
    xtdata_gateway: XtDataGateway,
    trading_manager: TradingSessionManager,
    trading_probe: bool = False,
) -> dict:
    """组装深度就绪快照。mock 模式下底层未连接属正常，仍视为就绪。"""

    data_health = xtdata_gateway.health_snapshot(probe=True)
    trading_health = trading_manager.health_snapshot(probe=trading_probe)
    ready = bool(data_health["ok"] and trading_health["ok"])
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "mode": settings.xtquant.mode.value,
        "components": {
            "xtdata": data_health,
            "xttrader": trading_health,
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/")
async def health_check(
    settings: Settings = Depends(get_settings),
    xtdata_gateway: XtDataGateway = Depends(get_xtdata_gateway),
    trading_manager: TradingSessionManager = Depends(get_trading_session_manager),
):
    """健康检查汇总接口（始终 200，含深度快照）。"""

    readiness = _build_readiness(settings, xtdata_gateway, trading_manager)
    return format_response(
        data={
            "status": "healthy" if readiness["ready"] else "degraded",
            "app_name": settings.app.name,
            "app_version": settings.app.version,
            "xtquant_mode": settings.xtquant.mode.value,
            "ready": readiness["ready"],
            "components": readiness["components"],
            "timestamp": readiness["timestamp"],
        },
        message="服务运行正常" if readiness["ready"] else "服务已启动但依赖未就绪",
    )


@router.get("/ready")
async def readiness_check(
    response: Response,
    trading_probe: bool = False,
    settings: Settings = Depends(get_settings),
    xtdata_gateway: XtDataGateway = Depends(get_xtdata_gateway),
    trading_manager: TradingSessionManager = Depends(get_trading_session_manager),
):
    """就绪检查接口：深度探测底层依赖，未就绪返回 503。

    查询参数 ``trading_probe=true`` 时会真正尝试连接一次交易终端（较重），
    默认仅检查交易端可用性与已注册账户，不建立真实连接。
    """

    readiness = _build_readiness(
        settings, xtdata_gateway, trading_manager, trading_probe=trading_probe
    )
    if not readiness["ready"]:
        response.status_code = 503
        return format_response(
            data=readiness,
            message="服务未就绪",
            success=False,
            code=503,
        )
    return format_response(data=readiness, message="服务已就绪")


@router.get("/live")
async def liveness_check():
    """存活检查接口：仅表示进程存活，不探测底层依赖。"""

    return format_response(
        data={"status": "alive", "timestamp": datetime.now().isoformat()},
        message="服务存活",
    )
