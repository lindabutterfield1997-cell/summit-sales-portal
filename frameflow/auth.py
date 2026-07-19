import hashlib
import hmac
import json
import os
import re
import secrets

import streamlit as st
import streamlit.components.v1 as components

from frameflow.formatting import today_iso
from frameflow.settings import AUTH_STORAGE_KEY, COMPANY_NAME
from frameflow.supabase_client import secret_or_env


DEFAULT_EMPLOYEE_ACCOUNTS = {
    "Mia": "frameflow-mia",
    "Ethan": "frameflow-ethan",
    "Zane": "frameflow-zane",
    "Tony": "frameflow-tony",
    "Liyao": "frameflow-liyao",
    "Kevin": "frameflow-kevin",
}
SALES_ACCOUNTS = ("Mia", "Ethan", "Zane", "Tony", "Liyao")
KNOWN_EMPLOYEE_NAMES = (*SALES_ACCOUNTS, "Kevin")


def admin_password() -> str:
    try:
        return str(st.secrets["ADMIN_PASSWORD"])
    except Exception:
        return os.getenv("ADMIN_PASSWORD", "frameflow-admin")


def employee_credentials() -> dict[str, str]:
    credentials: dict[str, str] = {}
    try:
        users = st.secrets["EMPLOYEE_USERS"]
        for username in users:
            credentials[str(username)] = str(users[username])
    except Exception:
        pass
    try:
        shared_password = str(st.secrets["EMPLOYEE_PASSWORD"])
    except Exception:
        shared_password = os.getenv("EMPLOYEE_PASSWORD", "")
    if shared_password:
        credentials.setdefault("team", shared_password)
    if not credentials:
        credentials.update(DEFAULT_EMPLOYEE_ACCOUNTS)
    return credentials


def using_default_employee_login() -> bool:
    return employee_credentials() == DEFAULT_EMPLOYEE_ACCOUNTS


def canonical_employee_name(username: str) -> str:
    cleaned = str(username or "").strip()
    lowered = cleaned.lower()
    if not lowered:
        return ""
    for known_name in KNOWN_EMPLOYEE_NAMES:
        if known_name.lower() == lowered:
            return known_name
    for stored_username in employee_credentials():
        if stored_username.lower() == lowered:
            return stored_username
    return cleaned


def manager_accounts() -> set[str]:
    try:
        configured = st.secrets["MANAGER_USERS"]
        if isinstance(configured, str):
            return {canonical_employee_name(configured)}
        return {
            canonical_employee_name(str(username))
            for username in configured
            if str(username).strip()
        }
    except Exception:
        raw = os.getenv("MANAGER_USERS", "")
    if raw:
        return {
            canonical_employee_name(username)
            for username in re.split(r"[,;\n]", raw)
            if username.strip()
        }
    return {"Kevin"} if using_default_employee_login() else set()


def current_employee_name() -> str:
    return canonical_employee_name(str(st.session_state.get("employee_name", "") or ""))


def is_manager_user(username: str | None = None) -> bool:
    name = canonical_employee_name(username or current_employee_name())
    return any(manager.lower() == name.lower() for manager in manager_accounts())


def customer_owner_filter() -> str:
    return "" if is_manager_user() else current_employee_name()


def customer_owner_options(current: str | None = "") -> tuple[str, ...]:
    current_value = canonical_employee_name(current or "")
    options = list(SALES_ACCOUNTS)
    for manager_name in sorted(manager_accounts()):
        if manager_name and manager_name not in options:
            options.append(manager_name)
    if current_value and current_value not in options:
        options.append(current_value)
    return tuple(options)


def default_customer_owner() -> str:
    employee = current_employee_name()
    if employee:
        return employee
    return SALES_ACCOUNTS[-1] if SALES_ACCOUNTS else ""


def valid_employee_login(username: str, password: str) -> bool:
    credentials = employee_credentials()
    username = username.strip()
    if username in credentials:
        return secrets.compare_digest(password, credentials[username])
    lowered = username.lower()
    for stored_username, stored_password in credentials.items():
        if stored_username.lower() == lowered:
            return secrets.compare_digest(password, stored_password)
    return False


def daily_auth_secret() -> str:
    configured = secret_or_env("DAILY_AUTH_SECRET")
    if configured:
        return configured
    credentials_blob = json.dumps(employee_credentials(), sort_keys=True)
    source = f"{credentials_blob}|{admin_password()}|{COMPANY_NAME}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def daily_auth_token(username: str, auth_day: str | None = None) -> str:
    normalized = canonical_employee_name(username)
    message = f"{auth_day or today_iso()}|{normalized}".encode("utf-8")
    return hmac.new(
        daily_auth_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def valid_daily_auth_token(
    username: str,
    token: str,
    auth_day: str | None = None,
) -> bool:
    normalized = canonical_employee_name(username)
    if not normalized or not token:
        return False
    known_users = {canonical_employee_name(name) for name in employee_credentials()}
    if normalized not in known_users:
        return False
    expected = daily_auth_token(normalized, auth_day or today_iso())
    return secrets.compare_digest(str(token), expected)


def persist_daily_login_script(username: str) -> None:
    normalized = canonical_employee_name(username)
    if not normalized:
        return
    payload = {
        "user": normalized,
        "day": today_iso(),
        "token": daily_auth_token(normalized),
    }
    components.html(
        f"""
        <script>
        (() => {{
          try {{
            const key = {json.dumps(AUTH_STORAGE_KEY)};
            const value = {json.dumps(json.dumps(payload))};
            window.parent.localStorage.setItem(key, value);
            window.parent.document.cookie = key + '=' + encodeURIComponent(value) + '; Max-Age=86400; Path=/; SameSite=Lax';
          }} catch (err) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def restore_daily_login_script() -> None:
    components.html(
        f"""
        <script>
        (() => {{
          try {{
            const key = {json.dumps(AUTH_STORAGE_KEY)};
            const cookieRaw = () => {{
              const prefix = key + '=';
              const found = (window.parent.document.cookie || '').split('; ').find(part => part.startsWith(prefix));
              return found ? decodeURIComponent(found.slice(prefix.length)) : '';
            }};
            const raw = window.parent.localStorage.getItem(key) || cookieRaw();
            if (!raw) return;
            const saved = JSON.parse(raw);
            const today = new Date().toISOString().slice(0, 10);
            if (!saved || saved.day !== today || !saved.user || !saved.token) {{
              window.parent.localStorage.removeItem(key);
              window.parent.document.cookie = key + '=; Max-Age=0; Path=/; SameSite=Lax';
              return;
            }}
            window.parent.localStorage.setItem(key, raw);
            const url = new URL(window.parent.location.href);
            if (url.searchParams.get('auth_user') === saved.user && url.searchParams.get('auth_token') === saved.token) return;
            url.searchParams.set('auth_user', saved.user);
            url.searchParams.set('auth_token', saved.token);
            window.parent.location.replace(url.toString());
          }} catch (err) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def clear_daily_login_script() -> None:
    components.html(
        f"""
        <script>
        (() => {{
          try {{
            const key = {json.dumps(AUTH_STORAGE_KEY)};
            window.parent.localStorage.removeItem(key);
            window.parent.document.cookie = key + '=; Max-Age=0; Path=/; SameSite=Lax';
          }} catch (err) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def query_param_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        return str(value[0] if value else "")
    return str(value or "")


def authenticate_from_daily_query() -> None:
    if st.session_state.get("employee_authenticated"):
        return
    username = query_param_value("auth_user")
    token = query_param_value("auth_token")
    if valid_daily_auth_token(username, token):
        st.session_state.employee_authenticated = True
        st.session_state.employee_name = canonical_employee_name(username)


def employee_login_page() -> None:
    restore_daily_login_script()
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Employee access</div>
          <h1>Employee Login</h1>
          <p>Sign in to view customer records, quotes, inventory, and service records.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if using_default_employee_login():
        st.warning(
            "Default sales accounts are active. Set EMPLOYEE_PASSWORD or "
            "[EMPLOYEE_USERS] in Secrets before publishing this website."
        )
    _, middle, _ = st.columns([1, 1.15, 1])
    with middle:
        with st.form("employee-login"):
            username = st.text_input(
                "Username",
                value="Liyao" if using_default_employee_login() else "",
            )
            password = st.text_input("Password", type="password")
            login = st.form_submit_button(
                "Sign in",
                type="primary",
                width="stretch",
            )
            if not login:
                return
            if not valid_employee_login(username, password):
                st.error("Incorrect username or password.")
                return

            normalized_username = canonical_employee_name(username)
            st.session_state.employee_authenticated = True
            st.session_state.employee_name = normalized_username
            st.session_state.active_customer_id = None
            st.session_state.cart = []
            persist_daily_login_script(normalized_username)
            try:
                st.query_params["auth_user"] = normalized_username
                st.query_params["auth_token"] = daily_auth_token(normalized_username)
            except Exception:
                pass
            st.rerun()
