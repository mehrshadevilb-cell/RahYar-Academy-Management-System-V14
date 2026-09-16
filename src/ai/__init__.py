"""RahYar AI package.

After `src/ai/provider_router.py` is present (from main), importing this
package applies the router 404/failover hardening so every code path that
uses AIProviderRouter inherits healthy-model selection.
"""

try:
    from src.ai import router_404_patch as _router_404_patch  # noqa: F401
except Exception:
    # provider_router may be missing until restored from main on this branch.
    _router_404_patch = None  # type: ignore

__all__ = ["router_404_patch"]
