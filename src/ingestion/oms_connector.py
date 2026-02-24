from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.ingestion.base_connector import TradeConnector
from src.models.database import TradeSource


class OMSConnector(TradeConnector):
    """Connector for OMS REST API."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get('OMS_API_URL', '')
        self.api_key = config.get('OMS_API_KEY', '')
        self.alpaca_key_id = config.get('ALPACA_API_KEY_ID', '')
        self.alpaca_secret_key = config.get('ALPACA_API_SECRET_KEY', '')
        self.is_alpaca = 'alpaca.markets' in self.api_url
        self.client: httpx.Client | None = None

    def connect(self) -> bool:
        if not self.api_url:
            logger.warning('OMS_API_URL not configured; skipping OMS ingestion')
            return False

        try:
            headers: dict[str, str]
            if self.is_alpaca:
                if not self.alpaca_key_id or not self.alpaca_secret_key:
                    logger.warning('ALPACA_API_KEY_ID/ALPACA_API_SECRET_KEY missing; skipping OMS ingestion')
                    return False
                headers = {
                    'APCA-API-KEY-ID': self.alpaca_key_id,
                    'APCA-API-SECRET-KEY': self.alpaca_secret_key,
                }
            else:
                headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}

            self.client = httpx.Client(
                base_url=self.api_url,
                headers=headers,
                timeout=30.0,
            )
            if self.is_alpaca:
                response = self.client.get('/v2/account')
                return response.status_code == 200

            response = self.client.get('/health')
            return response.status_code < 500
        except Exception as exc:
            logger.error(f'Failed to connect to OMS: {exc}')
            return False

    def fetch_trades(self, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        if self.client is None:
            return []

        try:
            if self.is_alpaca:
                response = self.client.get(
                    '/v2/orders',
                    params={
                        'status': 'filled',
                        'after': from_date.isoformat(),
                        'until': to_date.isoformat(),
                        'direction': 'asc',
                        'limit': 500,
                    },
                )
                response.raise_for_status()
                orders = response.json()
                logger.info(f'Fetched {len(orders)} Alpaca filled orders')
                return orders

            response = self.client.get(
                '/api/v1/trades',
                params={
                    'start_date': from_date.isoformat(),
                    'end_date': to_date.isoformat(),
                    'status': 'executed',
                },
            )
            response.raise_for_status()
            payload = response.json()
            trades = payload.get('trades', [])
            logger.info(f'Fetched {len(trades)} OMS trades')
            return trades
        except Exception as exc:
            logger.error(f'Error fetching OMS trades: {exc}')
            return []

    def normalize_trade(self, raw_trade: dict[str, Any]) -> dict[str, Any]:
        if self.is_alpaca:
            return self._normalize_alpaca_trade(raw_trade)

        execution_time = raw_trade.get('execution_time')
        settlement_date = raw_trade.get('settlement_date')

        return {
            'source_system': TradeSource.OMS,
            'source_trade_id': str(raw_trade.get('order_id') or raw_trade.get('id') or ''),
            'source_raw_data': raw_trade,
            'trade_date': datetime.fromisoformat(execution_time) if execution_time else datetime.utcnow(),
            'settlement_date': datetime.fromisoformat(settlement_date) if settlement_date else None,
            'symbol': str(raw_trade.get('ticker', '')).upper(),
            'security_identifier': raw_trade.get('isin'),
            'side': str(raw_trade.get('side', '')).upper(),
            'quantity': float(raw_trade.get('filled_quantity', 0)),
            'price': float(raw_trade.get('avg_fill_price', 0)),
            'gross_amount': float(raw_trade.get('gross_amount', 0)) if raw_trade.get('gross_amount') is not None else None,
            'net_amount': float(raw_trade.get('net_amount', 0)) if raw_trade.get('net_amount') is not None else None,
            'currency': raw_trade.get('currency', 'USD'),
            'counterparty': raw_trade.get('executing_broker'),
            'account_number': raw_trade.get('account'),
            'portfolio': raw_trade.get('portfolio'),
            'commission': float(raw_trade.get('commission', 0) or 0),
            'fees': float(raw_trade.get('fees', 0) or 0),
        }

    @staticmethod
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

    def _normalize_alpaca_trade(self, order: dict[str, Any]) -> dict[str, Any]:
        filled_at = self._parse_iso(order.get('filled_at')) or datetime.utcnow()
        qty = float(order.get('filled_qty') or 0)
        price = float(order.get('filled_avg_price') or 0)
        gross = qty * price
        side = str(order.get('side', '')).upper()

        return {
            'source_system': TradeSource.OMS,
            'source_trade_id': str(order.get('id') or order.get('client_order_id') or ''),
            'source_raw_data': order,
            'trade_date': filled_at,
            'settlement_date': None,
            'symbol': str(order.get('symbol', '')).upper(),
            'security_identifier': None,
            'side': side,
            'quantity': qty,
            'price': price,
            'gross_amount': gross,
            'net_amount': gross,
            'currency': 'USD',
            'counterparty': 'alpaca',
            'account_number': order.get('account_id'),
            'portfolio': None,
            'commission': 0.0,
            'fees': 0.0,
        }

    def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
