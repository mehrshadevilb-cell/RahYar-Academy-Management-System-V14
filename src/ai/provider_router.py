from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from src.core.config.settings import get_settings, normalize_openai_compatible_base_url

@dataclass(frozen=True)
class AIProvider:
    name: str
    api_key: str
    base_url: str
    models: tuple[str, ...]
    priority: int = 100
    enabled: bool = True
    provider_type: str = "openai_compatible"
    @property
    def model(self) -> str:
        return self.models[0] if self.models else ""

class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, retry_after: int = 0, provider: str = "") -> None:
        super().__init__(message); self.retryable = retryable; self.retry_after = max(0, retry_after); self.provider = provider

class AIProviderRouter:
    """Discover configured providers/models and route requests with failover."""
    def __init__(self) -> None:
        self.settings = get_settings(); self._cooldown_until: dict[str,float] = {}; self._model_cooldown_until: dict[str,float] = {}
        self._model_cache: dict[str, tuple[float, tuple[str,...]]] = {}
        self._model_cache_ttl = max(60, int(os.getenv("AI_MODEL_DISCOVERY_TTL_SECONDS", "600")))

    @staticmethod
    def _normalize_base_url(value: str) -> str: return normalize_openai_compatible_base_url((value or "").strip())
    @staticmethod
    def _infer_provider_type(name: str, base_url: str) -> str:
        host=(urlparse(base_url).hostname or "").lower(); x=f"{name} {host}".lower()
        if "generativelanguage.googleapis.com" in x or "google" in x or "gemini" in x: return "google"
        if "anthropic" in x or "claude" in x: return "anthropic"
        return "openai_compatible"
    @staticmethod
    def _is_free_model(model: Any) -> bool:
        if isinstance(model,str): x=model.lower(); return x.endswith(":free") or "-free" in x
        x=str(getattr(model,"model_id","") or "").lower(); return x.endswith(":free") or "-free" in x

    @classmethod
    def _provider_from_env(cls,name,key_var,url_var,model_var,priority):
        key=(os.getenv(key_var) or "").strip(); url=cls._normalize_base_url(os.getenv(url_var) or ""); model=(os.getenv(model_var) or "").strip()
        return AIProvider(name,key,url,(model,),priority,True,cls._infer_provider_type(name,url)) if key and url and model else None
    @staticmethod
    def _env_first(*names):
        for name in names:
            if name and (v:=os.getenv(name)): return v.strip()
        return ""
    def _catalog_path(self): return Path(os.getenv("AI_AGENT_REPO_PATH") or ".")/"config"/"ai_providers.json"
    def _load_catalog(self):
        try: payload=json.loads(self._catalog_path().read_text(encoding="utf-8"))
        except (OSError,ValueError,TypeError): return []
        rows=payload.get("providers",[]) if isinstance(payload,dict) else payload
        return rows if isinstance(rows,list) else []

    def _discover_models(self, provider: AIProvider, timeout: int=12) -> AIProvider:
        if provider.provider_type != "openai_compatible" or not provider.api_key: return provider
        key=f"{provider.name.lower()}|{provider.base_url}"; now=time.time(); cached=self._model_cache.get(key)
        if cached and cached[0]>now and cached[1]: return AIProvider(provider.name,provider.api_key,provider.base_url,cached[1],provider.priority,provider.enabled,provider.provider_type)
        req=urllib.request.Request(provider.base_url.rstrip("/")+"/models",headers=self._headers(provider),method="GET")
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r: payload=json.loads(r.read().decode("utf-8"))
            rows=payload.get("data",[]) if isinstance(payload,dict) else []
            if not rows and isinstance(payload,dict): rows=payload.get("models",[])
            ids=[]
            for row in rows if isinstance(rows,list) else []:
                mid=str(row.get("id") or row.get("name") or "").strip() if isinstance(row,dict) else str(row).strip()
                if mid and mid not in ids: ids.append(mid)
            if ids:
                models=tuple(ids); self._model_cache[key]=(now+self._model_cache_ttl,models)
                return AIProvider(provider.name,provider.api_key,provider.base_url,models,provider.priority,provider.enabled,provider.provider_type)
        except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,OSError,ValueError,TypeError,json.JSONDecodeError): pass
        return provider

    def _from_database(self):
        try:
            from src.database.models.ai_provider import AIProvider as DBProvider
            from src.database.session import SessionLocal
            from src.services.ai.credential_crypto import decrypt_api_key
            db=SessionLocal()
            try:
                out=[]
                for i,p in enumerate(db.query(DBProvider).filter(DBProvider.is_active.is_(True)).all()):
                    ms=[m for m in p.models if m.is_active]
                    if not ms: continue
                    ms.sort(key=lambda m:(not self._is_free_model(m),not m.is_default,-(m.context_window or 0),m.model_id))
                    try: key=decrypt_api_key(p.api_key_encrypted)
                    except Exception: continue
                    out.append(AIProvider(p.name,key,self._normalize_base_url(p.base_url),tuple(m.model_id for m in ms),i,True,p.provider_type or self._infer_provider_type(p.name,p.base_url)))
                return out
            finally: db.close()
        except Exception: return []

    def _catalog_providers(self):
        out=[]
        for i,row in enumerate(self._load_catalog()):
            if not isinstance(row,dict) or row.get("enabled",True) is False: continue
            name=str(row.get("name",f"catalog-{i}")); low=name.lower()
            key=self._env_first(str(row.get("api_key_env",""))) if row.get("api_key_env") else str(row.get("api_key","") or "")
            url=self._env_first(str(row.get("base_url_env",""))) if row.get("base_url_env") else str(row.get("base_url","") or "")
            if low=="opencode-zen": key=self._env_first("OPENCODE_ZEN_API_KEY","OPENCODE_API_KEY") or key; url=self._env_first("OPENCODE_ZEN_BASE_URL","OPENCODE_BASE_URL") or url
            if low=="openai": key=self._env_first("OPENAI_API_KEY") or key; url=self._env_first("OPENAI_BASE_URL") or url
            url=self._normalize_base_url(url)
            if not key or not url: continue
            models=tuple(str(x).strip() for x in row.get("models",[]) if str(x).strip()) if isinstance(row.get("models"),list) else ()
            p=AIProvider(name,key,url,models,int(row.get("priority",100)),True,str(row.get("provider_type","") or self._infer_provider_type(name,url)))
            out.append(self._discover_models(p) if not models else p)
        return out

    def _env_providers(self):
        out=[]; key=self._env_first("AGENTROUTER_API_KEY"); model=self._env_first("AI_MODEL","AI_AGENT_MODEL")
        if key and model: out.append(AIProvider("agentrouter",key,self._normalize_base_url(self._env_first("AI_BASE_URL") or "https://agentrouter.org/v1"),(model,),0))
        for p in (self._provider_from_env("primary","AI_API_KEY","AI_BASE_URL","AI_MODEL",10),self._provider_from_env("secondary","AI2_API_KEY","AI2_BASE_URL","AI2_MODEL",20)):
            if p: out.append(p)
        if not out and self.settings.effective_ai_api_key:
            base=self._normalize_base_url(self.settings.effective_ai_base_url); out.append(AIProvider("primary",self.settings.effective_ai_api_key,base,(self.settings.effective_ai_model,),100,True,self._infer_provider_type("primary",base)))
        return out

    @staticmethod
    def _merge_providers(providers):
        merged={}
        for p in providers:
            for m in p.models:
                k=(p.name.lower(),p.base_url.rstrip("/"),m)
                if k not in merged or p.priority<merged[k].priority: merged[k]=AIProvider(p.name,p.api_key,p.base_url,(m,),p.priority,p.enabled,p.provider_type)
        return sorted(merged.values(),key=lambda p:(not AIProviderRouter._is_free_model(p.model),p.priority,p.name,p.model))

    def _parse(self):
        configured=[]; raw=(self.settings.AI_PROVIDERS_JSON or "").strip()
        if raw:
            try: rows=json.loads(raw)
            except json.JSONDecodeError as exc: raise AIProviderError("AI_PROVIDERS_JSON is invalid JSON") from exc
            if not isinstance(rows,list): raise AIProviderError("AI_PROVIDERS_JSON must be a JSON array")
            for i,row in enumerate(rows):
                if not isinstance(row,dict) or row.get("enabled",True) is False: continue
                key=self._env_first(str(row.get("api_key_env",""))) if row.get("api_key_env") else str(row.get("api_key","") or "")
                url=self._env_first(str(row.get("base_url_env",""))) if row.get("base_url_env") else str(row.get("base_url","") or "")
                name=str(row.get("name",f"provider-{i+1}")); models=tuple(str(x).strip() for x in row.get("models",[]) if str(x).strip()) if isinstance(row.get("models"),list) else ()
                if not models and row.get("model"): models=(str(row["model"]).strip(),)
                url=self._normalize_base_url(url)
                if key and url:
                    p=AIProvider(name,key,url,models,int(row.get("priority",100)),True,str(row.get("provider_type","") or self._infer_provider_type(name,url))); configured.append(self._discover_models(p) if not models else p)
        result=self._merge_providers(configured+self._catalog_providers()+self._from_database()+self._env_providers())
        if not result: raise AIProviderError("No AI provider is configured")
        return result
    def providers(self): return self._parse()
    def reset_cooldowns(self): self._cooldown_until.clear(); self._model_cooldown_until.clear()
    def cooldown_snapshot(self):
        now=time.time(); return {k:max(0,int(v-now)) for k,v in self._model_cooldown_until.items() if v>now}
    def _headers(self,p):
        h={"Authorization":f"Bearer {p.api_key}","Content-Type":"application/json","Accept":"application/json","User-Agent":"RahYar-AIProviderRouter/1.7"}
        if (urlparse(p.base_url).hostname or "").lower().endswith("agentrouter.org"): h.update({"Originator":"codex_cli_rs","Version":"0.101.0"})
        return h
    @staticmethod
    def _anthropic_headers(p): return {"x-api-key":p.api_key,"anthropic-version":"2023-06-01","Content-Type":"application/json","Accept":"application/json","User-Agent":"RahYar-AIProviderRouter/1.7"}
    @staticmethod
    def _retry_after(headers,body):
        try: return max(1,int(float(headers.get("Retry-After") or headers.get("retry-after") or 0)))
        except (TypeError,ValueError): pass
        try: return max(1,int(float(json.loads(body).get("error",{}).get("metadata",{}).get("retry_after_seconds",0))))
        except (TypeError,ValueError,json.JSONDecodeError): return 0
    @staticmethod
    def _is_rate_limited(code,body): return code==429 or (code in {402,403} and any(x in body.lower() for x in ("rate","capacity","quota","limit")))
    def _ordered_candidates(self,providers): return [(p,m) for p in providers for m in p.models]

    @staticmethod
    def _extract_text(data,ptype):
        if ptype=="google": return " ".join(str(part.get("text","")) for c in data.get("candidates",[]) if isinstance(c,dict) for part in c.get("content",{}).get("parts",[]) if isinstance(part,dict)).strip() if isinstance(data,dict) else ""
        if ptype=="anthropic": return " ".join(str(x.get("text","")) for x in data.get("content",[]) if isinstance(x,dict)).strip() if isinstance(data,dict) else ""
        try: content=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError): return ""
        if isinstance(content,str): return content.strip()
        if isinstance(content,list): return " ".join(str(x.get("text","")) for x in content if isinstance(x,dict)).strip()
        return str(content).strip() if content else ""

    def _request(self,p,m,messages,kwargs,timeout):
        if p.provider_type=="google":
            payload={"contents":[{"role":"model" if x.get("role")=="assistant" else "user","parts":[{"text":str(x.get("content",""))}]} for x in messages if x.get("role")!="system"] or [{"role":"user","parts":[{"text":""}]}]}; url=p.base_url.rstrip("/")+f"/models/{quote(m,safe='')}:generateContent?key={quote(p.api_key,safe='')}"; headers={"Content-Type":"application/json"}
        elif p.provider_type=="anthropic":
            payload={"model":m,"max_tokens":int(kwargs.pop("max_tokens",4096)),"messages":[{"role":"assistant" if x.get("role")=="assistant" else "user","content":str(x.get("content",""))} for x in messages if x.get("role")!="system"] or [{"role":"user","content":""}]}; url=p.base_url.rstrip("/")+"/messages"; headers=self._anthropic_headers(p)
        else: payload={"model":m,"messages":messages,**kwargs}; url=p.base_url.rstrip("/")+"/chat/completions"; headers=self._headers(p)
        req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=headers,method="POST")
        with urllib.request.urlopen(req,timeout=timeout) as r: data=json.loads(r.read().decode())
        if not isinstance(data,dict) or not self._extract_text(data,p.provider_type): raise AIProviderError(f"AI provider returned an empty response: {p.name}/{m}",retryable=True,retry_after=30,provider=p.name)
        return data

    def _test_request(self,p,m,timeout):
        started=time.perf_counter(); self._request(p,m,[{"role":"user","content":"Reply with exactly: OK"}],{"max_tokens":8,"temperature":0},timeout); return 200,round((time.perf_counter()-started)*1000),"OK"
    def test_models(self,*,timeout_seconds=15):
        out=[]
        for p,m in self._ordered_candidates(self.providers()):
            started=time.perf_counter(); row={"provider":p.name,"model":m,"free":self._is_free_model(m),"ok":False,"latency_ms":0,"status":"unknown","response":""}
            try: status,lat,text=self._test_request(p,m,max(5,min(int(timeout_seconds),60))); row.update(ok=True,status="ok",http_status=status,latency_ms=lat,response=text)
            except urllib.error.HTTPError as e:
                body=""
                try: body=e.read().decode("utf-8",errors="replace")[:300]
                except Exception: pass
                row.update(status=f"http_{e.code}",http_status=e.code,retry_after=self._retry_after(e.headers,body))
            except Exception as e: row["status"]=f"unavailable:{type(e).__name__}"
            row["latency_ms"]=row["latency_ms"] or round((time.perf_counter()-started)*1000); out.append(row)
        return out

    def chat(self,messages,**kwargs):
        timeout=kwargs.pop("timeout_seconds",self.settings.AI_AGENT_TIMEOUT_SECONDS)
        try: timeout=max(5,min(int(timeout),120))
        except (TypeError,ValueError): timeout=60
        last=None; now=time.time()
        for p,m in self._ordered_candidates(self.providers()):
            key=f"{p.name}:{m}"
            if max(self._cooldown_until.get(p.name,0),self._model_cooldown_until.get(key,0))>now: continue
            try:
                data=self._request(p,m,messages,dict(kwargs),timeout); self._model_cooldown_until.pop(key,None); data.update(_rahyar_provider=p.name,_rahyar_model=m,_rahyar_is_free=self._is_free_model(m)); return data
            except urllib.error.HTTPError as e:
                body=""
                try: body=e.read().decode("utf-8",errors="replace")[:1000]
                except Exception: pass
                retry=self._retry_after(e.headers,body); cooldown=min(retry or (300 if self._is_rate_limited(e.code,body) else 60),86400); self._model_cooldown_until[key]=time.time()+cooldown; last=AIProviderError(f"provider request failed: {p.name}/{m} (HTTP {e.code})",retryable=e.code>=500 or self._is_rate_limited(e.code,body),retry_after=cooldown,provider=p.name)
            except (urllib.error.URLError,TimeoutError,OSError):
                self._model_cooldown_until[key]=time.time()+60; last=AIProviderError(f"provider unavailable: {p.name}/{m}",retryable=True,retry_after=60,provider=p.name)
            except AIProviderError as e:
                self._model_cooldown_until[key]=time.time()+(e.retry_after or 30); last=e
        raise last or AIProviderError("All configured AI models are temporarily unavailable",retryable=True,retry_after=30)
