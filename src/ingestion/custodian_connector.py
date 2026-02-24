from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd
from loguru import logger

from src.ingestion.base_connector import TradeConnector
from src.models.database import TradeSource

try:
    import paramiko
except ImportError:  # pragma: no cover - optional at runtime
    paramiko = None


class CustodianConnector(TradeConnector):
    """Connector for custodian CSV files over SFTP."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.sftp_host = config.get('CUSTODIAN_SFTP_HOST', '')
        self.sftp_user = config.get('CUSTODIAN_SFTP_USER', '')
        self.sftp_key_path = config.get('CUSTODIAN_SFTP_KEY', '')
        self.ssh = None
        self.sftp = None

    def connect(self) -> bool:
        if paramiko is None:
            logger.error('paramiko is not installed; cannot use custodian SFTP connector')
            return False

        if not self.sftp_host or not self.sftp_user or not self.sftp_key_path:
            logger.warning('Custodian SFTP config incomplete; skipping custodian ingestion')
            return False

        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            private_key = paramiko.RSAKey.from_private_key_file(self.sftp_key_path)
            self.ssh.connect(hostname=self.sftp_host, username=self.sftp_user, pkey=private_key)
            self.sftp = self.ssh.open_sftp()
            logger.info('Connected to custodian SFTP')
            return True
        except Exception as exc:
            logger.error(f'Failed to connect to custodian SFTP: {exc}')
            return False

    def fetch_trades(self, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        if self.sftp is None:
            return []

        try:
            remote_path = '/outbound/trades'
            files = self.sftp.listdir(remote_path)
            relevant_files: list[str] = []

            for filename in files:
                if filename.startswith('trades_') and filename.endswith('.csv'):
                    date_str = filename.replace('trades_', '').replace('.csv', '')
                    try:
                        file_date = datetime.strptime(date_str, '%Y%m%d')
                        if from_date.date() <= file_date.date() <= to_date.date():
                            relevant_files.append(filename)
                    except ValueError:
                        continue

            all_trades: list[dict[str, Any]] = []
            for filename in relevant_files:
                with self.sftp.file(f'{remote_path}/{filename}', 'r') as file_obj:
                    csv_content = file_obj.read().decode('utf-8')
                    df = pd.read_csv(StringIO(csv_content))
                    all_trades.extend(df.to_dict('records'))

            logger.info(f'Loaded {len(all_trades)} custodian trades from {len(relevant_files)} files')
            return all_trades
        except Exception as exc:
            logger.error(f'Error fetching custodian trades: {exc}')
            return []

    def normalize_trade(self, raw_trade: dict[str, Any]) -> dict[str, Any]:
        return {
            'source_system': TradeSource.CUSTODIAN,
            'source_trade_id': str(raw_trade.get('TradeID', '')),
            'source_raw_data': raw_trade,
            'trade_date': pd.to_datetime(raw_trade.get('TradeDate')).to_pydatetime(),
            'settlement_date': pd.to_datetime(raw_trade.get('SettleDate')).to_pydatetime(),
            'symbol': str(raw_trade.get('Symbol', '')).upper(),
            'security_identifier': raw_trade.get('CUSIP'),
            'side': 'BUY' if str(raw_trade.get('BuySellIndicator', '')).upper() == 'B' else 'SELL',
            'quantity': float(raw_trade.get('Quantity', 0)),
            'price': float(raw_trade.get('Price', 0)),
            'gross_amount': float(raw_trade.get('GrossAmount', 0)) if raw_trade.get('GrossAmount') is not None else None,
            'net_amount': float(raw_trade.get('NetAmount', 0)) if raw_trade.get('NetAmount') is not None else None,
            'currency': raw_trade.get('Currency', 'USD'),
            'counterparty': raw_trade.get('Counterparty'),
            'account_number': raw_trade.get('Account'),
            'portfolio': raw_trade.get('Portfolio'),
            'commission': float(raw_trade.get('Commission', 0) or 0),
            'fees': float(raw_trade.get('Fees', 0) or 0),
        }

    def disconnect(self) -> None:
        if self.sftp is not None:
            self.sftp.close()
        if self.ssh is not None:
            self.ssh.close()
