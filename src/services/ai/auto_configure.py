from __future__ import annotations

from src.services.ai.model_service import AIModelService
from src.services.ai.provider_bootstrap import AIProviderBootstrapService


def auto_configure_ai(session) -> dict:
    """Provision configured gateways, discover models, then pick a responding model."""
    bootstrap = AIProviderBootstrapService(session)
    providers = bootstrap.provision_configured()
    model_service = AIModelService(session)

    sync_results = model_service.sync_all_active_providers()
    selected = model_service.select_working_default()
    return {
        "providers": [provider.name for provider in providers],
        "sync": sync_results,
        "selected_provider": selected.provider.name if selected and selected.provider else None,
        "selected_model": selected.model_id if selected else None,
    }
