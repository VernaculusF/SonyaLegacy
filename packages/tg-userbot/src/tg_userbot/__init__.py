"""Sonya Telegram userbot package.

Telegram-specific transport adapter for the Sonya core. Implements the
`Channel` protocol from `sonya.channels.base`. Includes:
  - channel.py: the TelegramChannel class + media download + group rules
  - sticker_store.py: capture and re-send Telegram stickers

Loaded by `sonya.main._build_channels` via the auto-discovery sweep
across `packages/*/src/*/channel.py`.
"""
from __future__ import annotations
