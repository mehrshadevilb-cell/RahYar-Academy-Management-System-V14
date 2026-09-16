"""Backward-compatible import path.

Self-check is now part of admin_ai (ai_diagnostics / ai_self_check).
This module only re-exports the shared router so any leftover import
continues to work without registering a second router.
"""
from src.bot.handlers.admin_ai import router  # noqa: F401
