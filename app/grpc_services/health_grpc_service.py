"""
gRPC 健康检查服务实现

深度探测 xtdata 行情连接与 xttrader 交易可用性：任一依赖在 dev/prod 下未就绪时
返回 NOT_SERVING，与 REST /health/ready 语义保持一致。
"""

import grpc

from app.services.trading_session_manager import TradingSessionManager
from app.services.xtdata_gateway import XtDataGateway

# 导入生成的 protobuf 代码
from generated import health_pb2, health_pb2_grpc


class HealthGrpcService(health_pb2_grpc.HealthServicer):
    """gRPC 健康检查服务实现"""

    def __init__(
        self,
        xtdata_gateway: XtDataGateway | None = None,
        trading_manager: TradingSessionManager | None = None,
    ) -> None:
        self._xtdata_gateway = xtdata_gateway
        self._trading_manager = trading_manager

    def _is_serving(self) -> bool:
        # 未注入依赖时退化为浅层存活检查（保持向后兼容）。
        if self._xtdata_gateway is None or self._trading_manager is None:
            return True
        try:
            data_ok = self._xtdata_gateway.health_snapshot(probe=True)["ok"]
            trading_ok = self._trading_manager.health_snapshot(probe=False)["ok"]
        except Exception:
            return False
        return bool(data_ok and trading_ok)

    def Check(
        self, request: health_pb2.HealthCheckRequest, context: grpc.ServicerContext
    ) -> health_pb2.HealthCheckResponse:
        """健康检查"""
        status = (
            health_pb2.HealthCheckResponse.SERVING
            if self._is_serving()
            else health_pb2.HealthCheckResponse.NOT_SERVING
        )
        return health_pb2.HealthCheckResponse(status=status)
