from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from src.database.models.ai_model import AIModel
from src.database.models.ai_provider import AIProvider
from src.integrations.ai.registry import ProviderRegistry
from src.services.ai.credential_crypto import decrypt_api_key


class AIModelService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _run_async(coro):
        """Run provider I/O from both sync code and an active Telegram event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()

    def sync_models_for_provider(self, provider_id) -> dict[str, int]:
        provider = self.session.get(AIProvider, provider_id)
        if provider is None:
            raise ValueError("AI provider not found")
        if not provider.is_active:
            raise ValueError("AI provider is inactive")

        api_key = decrypt_api_key(provider.api_key_encrypted)
        client = ProviderRegistry.get_client(provider, api_key)
        discovered = self._run_async(client.list_models())
        if not isinstance(discovered, list):
            raise ValueError("AI provider returned an invalid model discovery payload")

        # Never interpret a transient/permission-limited empty response as proof
        # that every previously known model disappeared.
        valid_items = [item for item in discovered if isinstance(item, dict) and str(item.get("model_id") or "").strip()]
        if not valid_items:
            raise ValueError("AI provider returned no usable models; existing models were left unchanged")

        existing = {
            model.model_id: model
            for model in self.session.query(AIModel).filter(AIModel.provider_id == provider.id).all()
        }
        seen: set[str] = set()
        added = updated = 0

        for item in valid_items:
            model_id = str(item.get("model_id") or "").strip()
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

        deactivated = 0
        for model in existing.values():
            if model.model_id not in seen and model.is_active:
                model.is_active = False
                if model.is_default:
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
                results.append({"provider_id": str(provider.id), "ok": True, **result})
            except Exception as exc:
                self.session.rollback()
                results.append({"provider_id": str(provider.id), "ok": False, "error": str(exc)})
        return results

    def check_model(self, model_id) -> bool:
        """Make a minimal real completion to verify that a discovered model works."""
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

    def select_working_default(self) -> AIModel | None:
        """Prefer an actually responding model; fall back to capability/name ranking."""
        candidates = (
            self.session.query(AIModel)
            .filter(AIModel.is_active.is_(True))
            .order_by(AIModel.is_default.desc(), AIModel.context_window.desc().nullslast())
            .all()
        )
        for model in candidates:
            if self.check_model(model.id):
                return self.set_default(model.id)
        return None

    def set_default(self, model_id) -> AIModel:
        model = self.session.get(AIModel, model_id)
        if model is None:
            raise ValueError("AI model not found")
        if not model.is_active:
            raise ValueError("Inactive model cannot be default")
        self.session.query(AIModel).filter(
            AIModel.provider_id == model.provider_id,
            AIModel.id != model.id,
        ).update({AIModel.is_default: False}, synchronize_session=False)
        model.is_default = True
        self.session.commit()
        self.session.refresh(model)
        return model

    def get_default(self, provider_id=None) -> AIModel | None:
        query = self.session.query(AIModel).filter(
            AIModel.is_active.is_(True), AIModel.is_default.is_(True)
        )
        if provider_id is not None:
            query = query.filter(AIModel.provider_id == provider_id)
        return query.order_by(AIModel.updated_at.desc()).first()
