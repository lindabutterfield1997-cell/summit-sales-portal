import json
import os
from typing import Any
from urllib import error as url_error, parse, request as url_request

import streamlit as st


def secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.environ.get(name, default) or "").strip()


def configured() -> bool:
    return bool(
        secret_or_env("SUPABASE_URL")
        and (secret_or_env("SUPABASE_SERVICE_KEY") or secret_or_env("SUPABASE_KEY"))
    )


def api_key() -> str:
    return secret_or_env("SUPABASE_SERVICE_KEY") or secret_or_env("SUPABASE_KEY")


def base_url() -> str:
    raw_url = secret_or_env("SUPABASE_URL").strip().rstrip("/")
    if raw_url.endswith("/rest/v1"):
        raw_url = raw_url[: -len("/rest/v1")]
    parsed = parse.urlsplit(raw_url)
    if parsed.scheme and parsed.netloc and parsed.netloc.endswith(".supabase.co"):
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw_url


def request(
    method: str,
    table: str,
    query: str = "",
    payload: Any | None = None,
    prefer: str = "return=representation",
) -> Any:
    project_url = base_url()
    project_api_key = api_key()
    if not project_url or not project_api_key:
        raise RuntimeError("Supabase is not configured.")

    url = f"{project_url}/rest/v1/{table}"
    if query:
        url += f"?{query}"
    headers = {
        "apikey": project_api_key,
        "Authorization": f"Bearer {project_api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = url_request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with url_request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase request failed: {exc.code} {detail}") from exc
    except url_error.URLError as exc:
        raise RuntimeError(
            "Supabase connection failed. Please check SUPABASE_URL in Streamlit "
            "Secrets. It should look like https://your-project-ref.supabase.co"
        ) from exc

    return json.loads(body) if body else []

