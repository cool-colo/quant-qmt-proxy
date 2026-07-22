from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from app.config import Settings, get_settings
from app.dependencies import get_trading_session_manager, get_ui_subscription_service
from app.services.trading_session_manager import TradingSessionManager
from app.services.ui_subscription_service import UiSubscriptionService
from app.utils.exceptions import TradingServiceException
from app.utils.logger import logger

router = APIRouter(tags=["WebSocket"])
TRADING_STREAM_CLOSED = object()


def _validate_websocket_token(websocket: WebSocket, settings: Settings) -> bool:
    configured_keys = settings.security.api_keys
    if not configured_keys:
        return True
    return websocket.query_params.get("token") in configured_keys


def _next_trading_event(stream):
    try:
        return next(stream)
    except StopIteration:
        return TRADING_STREAM_CLOSED


@router.websocket("/ws/quote/{subscription_id}")
async def websocket_quote_stream(
    websocket: WebSocket,
    subscription_id: str,
    settings: Settings = Depends(get_settings),
    ui_subscription_service: UiSubscriptionService = Depends(get_ui_subscription_service),
):
    if not _validate_websocket_token(websocket, settings):
        logger.warning("WebSocket authentication failed: invalid token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    info = ui_subscription_service.get_subscription_info(subscription_id)
    if not info:
        logger.warning(f"WebSocket subscription not found: {subscription_id}")
        await websocket.send_json(
            {"type": "error", "message": f"missing-subscription: 订阅不存在 {subscription_id}"}
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info(f"WebSocket connected: subscription_id={subscription_id}")
    await websocket.send_json({"type": "connected", "subscription_id": subscription_id})
    stream = ui_subscription_service.stream_subscription(subscription_id)
    heartbeat_interval = max(settings.xtquant.data.heartbeat_interval, 0)
    next_event_task = asyncio.create_task(anext(stream))
    try:
        while True:
            try:
                if heartbeat_interval > 0:
                    done, _ = await asyncio.wait({next_event_task}, timeout=heartbeat_interval)
                    if not done:
                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "subscription_id": subscription_id,
                                "event_time_ms": int(time.time() * 1000),
                            }
                        )
                        continue
                    event = next_event_task.result()
                else:
                    event = await next_event_task
            except StopAsyncIteration:
                break
            await websocket.send_json({"type": "quote", "data": event})
            next_event_task = asyncio.create_task(anext(stream))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {subscription_id}")
    except Exception as exc:
        logger.error(f"WebSocket stream error: {exc}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        if not next_event_task.done():
            next_event_task.cancel()
            try:
                await next_event_task
            except BaseException:
                pass
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()


@router.websocket("/ws/trading/{session_id}")
async def websocket_trading_stream(
    websocket: WebSocket,
    session_id: str,
    settings: Settings = Depends(get_settings),
    trading_manager: TradingSessionManager = Depends(get_trading_session_manager),
):
    if not _validate_websocket_token(websocket, settings):
        logger.warning("Trading WebSocket authentication failed: invalid token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        stream = trading_manager.stream_events(session_id)
    except TradingServiceException as exc:
        logger.warning(f"Trading WebSocket session not found: session_id={session_id}")
        await websocket.send_json({"type": "error", "message": exc.message})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info(f"Trading WebSocket connected: session_id={session_id}")
    await websocket.send_json({"type": "connected", "session_id": session_id})
    heartbeat_interval = max(settings.xtquant.data.heartbeat_interval, 0)
    next_event_task = asyncio.create_task(asyncio.to_thread(_next_trading_event, stream))
    try:
        while True:
            try:
                if heartbeat_interval > 0:
                    done, _ = await asyncio.wait({next_event_task}, timeout=heartbeat_interval)
                    if not done:
                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "session_id": session_id,
                                "event_time_ms": int(time.time() * 1000),
                            }
                        )
                        continue
                    event = next_event_task.result()
                else:
                    event = await next_event_task
            except StopAsyncIteration:
                break

            if event is TRADING_STREAM_CLOSED:
                break
            await websocket.send_json({"type": "trading", "data": event})
            next_event_task = asyncio.create_task(asyncio.to_thread(_next_trading_event, stream))
    except WebSocketDisconnect:
        logger.info(f"Trading WebSocket disconnected: session_id={session_id}")
    except Exception as exc:
        logger.error(f"Trading WebSocket stream error: {exc}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        stream.close()
        if not next_event_task.done():
            next_event_task.cancel()
            try:
                await next_event_task
            except BaseException:
                pass
