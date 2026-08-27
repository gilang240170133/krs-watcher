from __future__ import annotations

import logging

import requests

log = logging.getLogger("krs_watcher.telegram")

API_BASE = "https://api.telegram.org"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timeout: int = 15):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diisi di config.py")
            return False

        url = f"{API_BASE}/bot{self.bot_token}/sendMessage"
        try:
            resp = requests.post(
                url,
                data={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                log.error(
                    "Gagal kirim notif: HTTP %s -- %s",
                    resp.status_code,
                    resp.text[:300],
                )
                return False
            return True
        except requests.RequestException as e:
            log.error("Gagal kirim notif: %s", e)
            return False
