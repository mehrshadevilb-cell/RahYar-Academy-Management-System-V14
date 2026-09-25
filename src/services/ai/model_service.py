from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from src.database.models.ai_model import AIModel
from src.database.models.ai_provider import AIProvider
from src.integrations.ai.registry import ProviderRegistry
from src.services.ai.credential_crypto import decrypt_api_key
from src.core.config.settings import get_settings


class AIModelService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _run_async(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()

    @staticmethod
    def is_free(model: AIModel) -> bool:
        raw = model.raw_metadata or {}
        model_id = model.model_id.lower()
        if model_id.endswith(":free") or "-free" in model_id:
            return True
        pricing = raw.get("pricing") if isinstance(raw, dict) else None
        if isinstance(pricing, dict):
            prompt = pricing.get("prompt", pricing.get("input"))
            completion = pricing.get("completion", pricing.get("output"))
            try:
                if prompt is not None and completion is not None:
                    return float(prompt) == 0.0 and float(completion) == 0.0
            except (TypeError, ValueError):
                pass
        try:
            return (
                model.pricing_input is not None
                and model.pricing_output is not None
                and float(model.pricing_input) == 0.0
                and float(model.pricing_output) == 0.0
            )
        except (TypeError, ValueError):
            return False

    def sync_models_for_provider(self, provider_id) -> dict[str, int]:
        provider = self.session.get(AIProvider, provider_id)
        if provider is None:
            raise ValueError("AI provider not found")
        if not provider.is_active:
            raise ValueError("AI provider is inactive")
        client = ProviderRegistry.get_client(provider, decrypt_api_key(provider.api_key_encrypted))
        discovery_error: Exception | None = None
        try:
            discovered = self._run_async(client.list_models())
        except Exception as exc:
            discovery_error = exc
            discovered = []

        if not isinstance(discovered, list):
            discovered = []

        # Some gateways (notably Bytez) can reject their catalog endpoint even
        # while a configured model is callable. Keep that explicit model as a
        # temporary runtime candidate; the normal health probe/router will still
        # reject it immediately if the credential or model is actually unusable.
        if not discovered:
            configured_model = str(
                getattr(get_settings(), f"{provider.name.upper().replace('-', '_')}_MODEL", "") or ""
            ).strip()
            if configured_model:
                discovered = [{
                    "model_id": configured_model,
                    "display_name": configured_model,
                    "raw_metadata": {"discovery_fallback": True},
                }]
            elif discovery_error is not None:
                raise discovery_error

        valid_items: list[dict] = []
        for item in discovered:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("model_id") or item.get("id") or "").strip()
            if not model_id:
                continue
            normalized = dict(item)
            normalized["model_id"] = model_id
            valid_items.append(normalized)

        if not valid_items:
            raise ValueError("AI provider returned no usable models; existing models were left unchanged")

        existing = {m.model_id: m for m in self.session.query(AIModel).filter(AIModel.provider_id == provider.id).all()}
        seen: set[str] = set()
        added = updated = deactivated = 0
        for item in valid_items:
            model_id = item["model_id"]
            seen.add(model_id)
            model = existing.get(model_id)
            if model is None:
                model = AIModel(provider_id=provider.id, model_id=model_id)
                self.session.add(model)
                added += 1
            else:
                updated += 1
            model.display_name = str(item.get("display_name") or model_id)
            model.context_window = item.get("context_window")
            model.max_output_tokens = item.get("max_output_tokens")
            model.supports_vision = bool(item.get("supports_vision", provider.supports_vision))
            model.supports_tools = bool(item.get("supports_tools", provider.supports_tools))
            model.supports_streaming = bool(item.get("supports_streaming", provider.supports_streaming))
            model.pricing_input = item.get("pricing_input")
            model.pricing_output = item.get("pricing_output")
            model.raw_metadata = item.get("raw_metadata") or {}
            model.is_active = True
            model.last_seen_at = datetime.now(timezone.utc)

        for model in existing.values():
            if model.model_id not in seen and model.is_active:
                if model.is_default:
                    continue
                model.is_active = False
                model.is_default = False
                deactivated += 1
        provider.last_models_sync_at = datetime.now(timezone.utc)
        self.session.commit()
        return {"added": added, "updated": updated, "deactivated": deactivated, "total": len(seen)}

    def sync_all_active_providers(self) -> list[dict]:
        results = []
        for provider in self.session.query(AIProvider).filter(AIProvider.is_active.is_(True)).all():
            try:
                result = self.sync_models_for_provider(provider.id)
                results.append({"provider_id": str(provider.id), "provider": provider.name, "ok": True, **result})
            except Exception as exc:
                self.session.rollback()
                results.append({"provider_id": str(provider.id), "provider": provider.name, "ok": False, "error": str(exc)})
        return results

    def check_model(self, model_id) -> bool:
        model = self.session.get(AIModel, model_id)
        if model is None or not model.is_active:
            return False
        provider = self.session.get(AIProvider, model.provider_id)
        if provider is None or not provider.is_active:
            return False
        client = ProviderRegistry.get_client(provider, decrypt_api_key(provider.api_key_encrypted))
        try:
            result = self._run_async(
                client.chat_completion(
                    model.model_id,
                    [{"role": "user", "content": "Reply with OK."}],
                    max_tokens=4,
                    temperature=0,
                )
            )
            return isinstance(result, dict) and bool(result)
        except Exception:
            return False

    def scan_working_models(self) -> dict:
        """Probe every discovered active model and persist a lightweight health marker.

        This intentionally uses a tiny completion request so the router can prefer
        models that have actually responded recently. The normal runtime router
        still performs immediate failover if a model becomes unavailable later.
        """
        models = (
            self.session.query(AIModel)
            .join(AIProvider, AIProvider.id == AIModel.provider_id)
            .filter(AIModel.is_active.is_(True), AIProvider.is_active.is_(True))
            .all()
        )
        working: list[AIModel] = []
        failed: list[AIModel] = []
        for model in models:
            ok = self.check_model(model.id)
            metadata = dict(model.raw_metadata or {})
            metadata["health"] = {
                "working": ok,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            model.raw_metadata = metadata
            if ok:
                working.append(model)
            else:
                failed.append(model)
        self.session.commit()

        return {
            "checked": len(models),
            "working": len(working),
            "failed": len(failed),
            "working_models": [f"{m.provider.name}:{m.model_id}" for m in working],
            "failed_models": [f"{m.provider.name}:{m.model_id}" for m in failed],
        }

    def select_working_default(self) -> AIModel | None:
        candidates = (
            self.session.query(AIModel)
            .join(AIProvider, AIProvider.id == AIModel.provider_id)
            .filter(AIModel.is_active.is_(True), AIProvider.is_active.is_(True))
            .order_by(AIModel.context_window.desc().nullslast())
            .all()
        )
        free = [m for m in candidates if self.is_free(m)]
        paid = [m for m in candidates if not self.is_free(m)]
        for model in free + paid:
            if self.check_model(model.id):
                return self.set_default(model.id)
        return None

    def set_default(self, model_id) -> AIModel:
        model = self.session.get(AIModel, model_id)
        if model is None or not model.is_active:
            raise ValueError("Active AI model not found")
        self.session.query(AIModel).filter(AIModel.provider_id == model.provider_id, AIModel.id != model.id).update({AIModel.is_default: False}, synchronize_session=False)
        model.is_default = True
        self.session.commit()
        self.session.refresh(model)
        return model

    def get_default(self, provider_id=None) -> AIModel | None:
        query = self.session.query(AIModel).filter(AIModel.is_active.is_(True), AIModel.is_default.is_(True))
        if provider_id is not None:
            query = query.filter(AIModel.provider_id == provider_id)
        return query.order_by(AIModel.updated_at.desc()).first()
