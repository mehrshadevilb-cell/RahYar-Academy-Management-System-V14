"""RahYar AI package.

Importing this package applies the router 404/failover hardening so every
code path that uses AIProviderRouter inherits healthy-model selection.
"""

from src.ai import router_404_patch as _router_404_patch  # noqa: F401

__all__ = ["router_404_patch"]
