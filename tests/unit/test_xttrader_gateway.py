from __future__ import annotations

import app.services.xttrader_gateway as xttrader_gateway_module

from app.services.xttrader_gateway import XTTraderGateway


def test_gateway_uses_two_argument_constructor_for_xtquant_big_convert_compat(monkeypatch):
    constructor_args: tuple[object, ...] | None = None

    class FakeTrader:
        def __init__(self, *args):
            nonlocal constructor_args
            constructor_args = args
            self.callback = None

        def register_callback(self, callback):
            self.callback = callback

        def start(self):
            return 0

        def connect(self):
            return 0

        def subscribe(self, account):
            return 0

    class FakeAccount:
        def __init__(self, account_id, account_type):
            self.account_id = account_id
            self.account_type = account_type

    monkeypatch.setattr(xttrader_gateway_module, "XTQUANT_TRADER_AVAILABLE", True)
    monkeypatch.setattr(xttrader_gateway_module, "XtQuantTrader", FakeTrader)
    monkeypatch.setattr(xttrader_gateway_module, "StockAccount", FakeAccount)
    gateway = XTTraderGateway("C:/fake-qmt", "SIM-001")

    gateway.connect()

    assert constructor_args == ("C:/fake-qmt", gateway.session)
    assert gateway.trader.callback is gateway.callback
