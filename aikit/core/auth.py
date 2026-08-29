from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, Request
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid

logger = logging.getLogger("aikit")


@dataclass
class PrincipalConfig:
	method: str = "cookie"
	allow_anonymous: bool = True
	anonymous_principal: str = "anon"
	proxy: Dict[str, Any] = field(default_factory=dict)
	jwt: Dict[str, Any] = field(default_factory=dict)
	cookie: Dict[str, Any] = field(default_factory=dict)


def _b64url_encode(raw: bytes) -> str:
	return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
	pad = "=" * ((4 - len(value) % 4) % 4)
	return base64.urlsafe_b64decode(value + pad)


def _resolve_secret(cfg: Dict[str, Any], default_env: str) -> Optional[str]:
	"""Prioriza la variable de entorno; el YAML solo debería usarse en desarrollo."""
	env_name = str(cfg.get("secret_env", default_env) or default_env).strip()
	secret = os.getenv(env_name, "")
	if not secret:
		secret = str(cfg.get("secret", "") or "")
	secret = secret.strip()
	return secret or None


def _hmac_sha256(secret: str, payload: bytes) -> bytes:
	return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()


def _verify_jwt_hs256(token: str, cfg: Dict[str, Any]) -> Optional[str]:
	"""Validación mínima de JWT firmado con clave simétrica (HS256)."""
	secret = _resolve_secret(cfg, "AIKIT_JWT_SECRET")
	if not secret:
		logger.warning("auth.method=jwt but no secret configured")
		return None

	parts = token.split(".")
	if len(parts) != 3:
		return None

	signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
	try:
		header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
		payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
		signature = _b64url_decode(parts[2])
	except Exception:
		return None

	if str(header.get("alg", "")).upper() != "HS256":
		return None
	if not hmac.compare_digest(signature, _hmac_sha256(secret, signing_input)):
		return None

	exp = payload.get("exp")
	if isinstance(exp, (int, float)) and time.time() > float(exp):
		return None

	issuer = str(cfg.get("issuer", "") or "").strip()
	if issuer and str(payload.get("iss", "")) != issuer:
		return None

	audience = str(cfg.get("audience", "") or "").strip()
	if audience:
		aud = payload.get("aud")
		aud_values = aud if isinstance(aud, list) else [aud]
		if audience not in [str(x) for x in aud_values]:
			return None

	claim_name = str(cfg.get("claim_name", "sub") or "sub").strip()
	value = payload.get(claim_name)
	return value.strip() if isinstance(value, str) and value.strip() else None


def issue_session_token(principal_id: str, secret: str, max_age_seconds: int) -> str:
	"""Token opaco 'payload.firma' con HMAC-SHA256; el secreto nunca sale del backend."""
	payload = json.dumps(
		{"sub": principal_id, "exp": int(time.time()) + int(max_age_seconds)},
		separators=(",", ":"),
	).encode("utf-8")
	encoded = _b64url_encode(payload)
	signature = _b64url_encode(_hmac_sha256(secret, encoded.encode("ascii")))
	return f"{encoded}.{signature}"


def verify_session_token(token: str, secret: str) -> Optional[str]:
	parts = token.split(".")
	if len(parts) != 2:
		return None

	encoded, signature = parts
	try:
		expected = _hmac_sha256(secret, encoded.encode("ascii"))
		if not hmac.compare_digest(_b64url_decode(signature), expected):
			return None
		payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
	except Exception:
		return None

	exp = payload.get("exp")
	if not isinstance(exp, (int, float)) or time.time() > float(exp):
		return None

	sub = payload.get("sub")
	return sub.strip() if isinstance(sub, str) and sub.strip() else None


def build_session_config(cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
	"""Devuelve (config de cookie, secreto) para el endpoint de sesión."""
	auth_cfg = cfg.get("auth", {}) if isinstance(cfg, dict) else {}
	if not isinstance(auth_cfg, dict) or str(auth_cfg.get("method", "")).strip().lower() != "cookie":
		return {}, None
	cookie_cfg = auth_cfg.get("cookie", {})
	if not isinstance(cookie_cfg, dict):
		cookie_cfg = {}
	return cookie_cfg, _resolve_secret(cookie_cfg, "AIKIT_SESSION_SECRET")


def new_principal_id(prefix: str = "web") -> str:
	return f"{prefix}-{uuid.uuid4().hex}"


def _section(auth_cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
	section = auth_cfg.get(name, {})
	return section if isinstance(section, dict) else {}


def _bearer_token(request: Request) -> str:
	authz = request.headers.get("authorization", "")
	return authz.split(" ", 1)[1].strip() if authz.lower().startswith("bearer ") else ""


def _principal_from_proxy(request: Request, p: PrincipalConfig) -> Optional[str]:
	"""El gateway ya ha autenticado y reinyecta la identidad; debe borrar la cabecera del cliente."""
	header_name = str(p.proxy.get("userid_header", "x-user-id") or "x-user-id").strip().lower()
	value = request.headers.get(header_name)
	return value.strip() if isinstance(value, str) and value.strip() else None


def _principal_from_jwt(request: Request, p: PrincipalConfig) -> Optional[str]:
	token = _bearer_token(request)
	return _verify_jwt_hs256(token, p.jwt) if token else None


def _principal_from_cookie(request: Request, p: PrincipalConfig) -> Optional[str]:
	secret = _resolve_secret(p.cookie, "AIKIT_SESSION_SECRET")
	if not secret:
		logger.warning("auth.method=cookie but no session secret configured")
		return None

	cookie_name = str(p.cookie.get("cookie_name", "aikit_session") or "aikit_session").strip()
	token_header = str(p.cookie.get("token_header", "x-session-token") or "x-session-token").strip().lower()
	token = request.cookies.get(cookie_name) or request.headers.get(token_header, "")
	return verify_session_token(token.strip(), secret) if isinstance(token, str) and token.strip() else None


def resolve_principal(request: Request, cfg: Dict[str, Any]) -> str:
	auth_cfg = cfg.get("auth", {}) if isinstance(cfg, dict) else {}
	if not isinstance(auth_cfg, dict):
		auth_cfg = {}

	p = PrincipalConfig(
		method=str(auth_cfg.get("method", "cookie")).strip().lower() or "cookie",
		allow_anonymous=bool(auth_cfg.get("allow_anonymous", True)),
		anonymous_principal=str(auth_cfg.get("anonymous_principal", "anon")).strip() or "anon",
		proxy=_section(auth_cfg, "proxy"),
		jwt=_section(auth_cfg, "jwt"),
		cookie=_section(auth_cfg, "cookie"),
	)

	resolvers = {
		"proxy": _principal_from_proxy,
		"jwt": _principal_from_jwt,
		"cookie": _principal_from_cookie,
	}
	resolver = resolvers.get(p.method)
	if resolver is None:
		raise HTTPException(status_code=500, detail=f"Unknown auth.method: {p.method}")

	principal_id = resolver(request, p)
	if principal_id:
		return principal_id

	if p.allow_anonymous:
		return p.anonymous_principal

	raise HTTPException(status_code=401, detail="Authentication required")
