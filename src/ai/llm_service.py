import json
import os
import traceback
from typing import Optional

_last_api_error = None

def diagnostics() -> dict:
    cfg = _load_config()
    return {
        "provider": cfg["provider"],
        "model": cfg["model"],
        "api_key_detected": bool(cfg["api_key"]),
        "last_api_error": _last_api_error,
    }

def _load_config() -> dict:
    return {
        "provider": os.getenv("AI_PROVIDER", "gemini").lower(),
        "api_key": os.getenv("AI_API_KEY", ""),
        "model": os.getenv("AI_MODEL", "gemini-2.0-flash"),
        "timeout": int(os.getenv("AI_TIMEOUT", "30")),
    }

def _build_prompt(data: dict) -> str:
    probas_str = ", ".join([f"{k}: {v:.0%}" for k, v in data.get("probas", {}).items()])
    return f"""Tu es un expert en prévention des incendies de forêt au Maroc, région d'Agdez (Drâa-Tafilalet).

Analyse ce risque incendie et réponds UNIQUEMENT avec un objet JSON valide contenant exactement 3 clés :

1. "explication" : explication détaillée en français de la prédiction (pourquoi ce niveau, facteurs déterminants, tendance).
2. "sensibilisation" : message de sensibilisation pour la population locale, adapté au niveau de risque.
3. "bulletin" : bulletin opérationnel court pour les autorités (pompiers, protection civile), avec recommandations concrètes.

---

**Données actuelles :**
- Risque prédit : {data.get("risque", "N/A")}
- Confiance du modèle : {data.get("confiance", 0):.0%}
- Température : {data.get("temperature", "N/A")}°C
- Humidité : {data.get("humidite", "N/A")}%
- Précipitations : {data.get("precipitation", "N/A")} mm
- Vent : {data.get("vent", "N/A")} m/s
- NDVI (végétation) : {data.get("ndvi", "N/A")}
- Mois : {data.get("mois", "N/A")} {data.get("annee", "N/A")}
- Altitude : {data.get("altitude", "N/A")} m · Pente : {data.get("pente", "N/A")}°
- Probabilités : {probas_str}

**Format de réponse attendu (JSON strict, sans balises markdown) :**
{{"explication": "texte...", "sensibilisation": "texte...", "bulletin": "texte..."}}"""

def _appel_gemini(cfg: dict, prompt: str) -> Optional[dict]:
    import requests
    api_key = cfg["api_key"]
    if not api_key:
        return None
    model = cfg.get("model", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
        }
    }
    r = requests.post(url, json=body, timeout=cfg["timeout"])
    if r.status_code == 403:
        raise PermissionError("Clé API Gemini invalide")
    if r.status_code == 429:
        try:
            err_body = r.json()
            err_msg = err_body.get("error", {}).get("message", "Quota dépassé")
        except Exception:
            err_msg = "Quota API Gemini dépassé (Rate Limit)"
        raise PermissionError(f"Gemini quota exceeded: {err_msg}")
    r.raise_for_status()
    candidates = r.json().get("candidates", [])
    if not candidates:
        return None
    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return _parser_reponse(text)

def _appel_openai(cfg: dict, prompt: str) -> Optional[dict]:
    import requests
    api_key = cfg["api_key"]
    if not api_key:
        return None
    model = cfg.get("model", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(url, json=body, headers=headers, timeout=cfg["timeout"])
    if r.status_code == 401:
        raise PermissionError("Clé API OpenAI invalide")
    if r.status_code == 429:
        raise ConnectionError("Quota API OpenAI dépassé")
    r.raise_for_status()
    text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parser_reponse(text)

def _parser_reponse(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        debut = text.index("{")
        fin = text.rindex("}") + 1
        return json.loads(text[debut:fin])
    except (ValueError, json.JSONDecodeError):
        return None

def analyse_ia(prompt_data: dict) -> dict:
    global _last_api_error
    cfg = _load_config()
    if not cfg["api_key"]:
        _last_api_error = "AI_API_KEY manquante dans .env"
        return {"erreur": _last_api_error, "fallback": True}
    prompt = _build_prompt(prompt_data)
    provider = cfg["provider"]
    result = None
    try:
        if provider == "gemini":
            result = _appel_gemini(cfg, prompt)
        elif provider == "openai":
            result = _appel_openai(cfg, prompt)
        else:
            raise ValueError(f"Fournisseur AI inconnu : {provider}")
    except Exception as e:
        err_str = f"{type(e).__name__}: {e}"
        is_quota = any(kw in str(e).lower() for kw in ["quota", "resource exhausted", "429", "rate limit"])
        _last_api_error = err_str
        return {
            "erreur": err_str,
            "fallback": True,
            "quota_exceeded": is_quota,
        }
    _last_api_error = None
    if result and all(k in result for k in ("explication", "sensibilisation", "bulletin")):
        return result
    if result:
        result.setdefault("explication", "")
        result.setdefault("sensibilisation", "")
        result.setdefault("bulletin", "")
        return result
    _last_api_error = "Réponse API invalide ou vide"
    return {"erreur": _last_api_error, "fallback": True}
