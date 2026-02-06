import json
import os
import re
import time
import datetime
import logging
import ast
from typing import Dict, Any, Optional, List, Union

import requests
import boto3
from botocore.exceptions import ClientError


# =========================
# Configuration (O11)
# =========================
class Config:
    # ---------- Rootly ----------
    ROOTLY_API_TOKEN = os.environ.get('ROOTLY_API_TOKEN', '')
    ROOTLY_BASE_URL = 'https://api.rootly.com'

    # ---------- Rundeck ----------
    RUNDECK_API_TOKEN = os.environ.get('RUNDECK_API_TOKEN_Dev', '')
    RUNDECK_URL = os.environ.get('RUNDECK_URL', 'https://rundeck-dev.outsystems.com/api/45')
    RUNDECK_PROJECT = os.environ.get('RUNDECK_PROJECT', 'O11')
    GITHUB_ACTION_ID = os.environ.get('GITHUB_ACTION_ID', '2c367a7e-ef02-11ed-a05b-0242ac120003')

    # ---------- Polling / backoff ----------
    POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', '6'))
    MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '40'))

    # ---------- DynamoDB ----------
    DDB_TABLE = os.environ.get('DYNAMODB_TABLE', 'ProcessedIncidentsTable')
    REM_GUARD_TTL = int(os.environ.get("GUARD_TTL_SECONDS", "5"))
    AUTO_DEDUPE_TTL = int(os.environ.get("AUTO_DEDUPE_TTL", "300"))
    MIRROR_DEDUPE_TTL = int(os.environ.get("MIRROR_DEDUPE_TTL", "300"))

    # Lambda self invoke (async poll)
    LAMBDA_FUNCTION_NAME = os.environ.get('ASYNC_POLL_LAMBDA_NAME', '')

    # ---------- In-code defaults (overridden by AppConfig) ----------
    REMEDIATION_JOB_ID_MAP: Dict[str, str] = {}

    # Optional named diagnosis jobs (rarely used for O11 manual)
    DIAGNOSIS_JOB_ID_MAP: Dict[str, str] = {}

    # Auto diagnosis routing is driven by watch_id
    DEFAULT_WATCH_TO_DIAG_MAP: Dict[str, str] = {}
    WATCH_TO_DIAG_MAP = {
        re.sub(r'[^a-z0-9]+', '_', (k or '').strip().lower()).strip('_'): v
        for k, v in {**DEFAULT_WATCH_TO_DIAG_MAP,
                    **json.loads(os.environ.get("WATCH_TO_DIAG_MAP", "{}"))}.items()
    }

    REMEDIATION_DEFAULT_OPTION_MAP = {
        "data.custom_fields.environment_orn": "env_orn",
        "data.custom_fields.asset": "asset"
    }

    # Shrunk set for diagnosis only (minimal + env/watch)
    DIAGNOSIS_DEFAULT_OPTION_MAP = {
        "data.custom_fields.environment_orn": "env_orn",
    }

    RUNDECK_OPTION_MAP = json.loads(os.environ.get("RUNDECK_OPTION_MAP", "{}"))

    PASS_ALL_CUSTOM_FIELDS = os.environ.get("PASS_ALL_CUSTOM_FIELDS", "false").lower() == "true"

    MIRROR_FIELD_NAME = os.environ.get("MIRROR_FIELD_NAME", "Mirror Ready Token")
    MIRROR_FIELD_ID = os.environ.get("MIRROR_FIELD_ID", "").strip()
    MIRROR_FIELD_SLUG = os.environ.get("MIRROR_FIELD_SLUG", "").strip()
    MIRROR_TOKEN_PREFIX = (os.environ.get("MIRROR_TOKEN_PREFIX", "mrr").strip() or "mrr")

    TIMEOUT = int(os.environ.get("HTTP_TIMEOUT_SECONDS", "30"))

    # Preflight for auto diagnosis
    REQUIRED_AUTO_DIAGNOSIS_OPTIONS: List[str] = json.loads(
        os.environ.get("REQUIRED_AUTO_DIAGNOSIS_OPTIONS", '["env_orn"]')
    )

    FAIL_OPEN_ON_DDB_ERROR = os.environ.get("FAIL_OPEN_ON_DDB_ERROR", "false").lower() == "true"

    # ---------- AppConfig ----------
    APPCONFIG_APP_ID = os.environ.get("APPCONFIG_APP_ID", "")
    APPCONFIG_ENV_ID = os.environ.get("APPCONFIG_ENV_ID", "")
    APPCONFIG_PROFILE_ID = os.environ.get("APPCONFIG_PROFILE_ID", "")
    APPCONFIG_CACHE_SECONDS = int(os.environ.get("APPCONFIG_CACHE_SECONDS", "60"))


# =========================
# Structured Logging
# =========================
class Log:
    _logger = logging.getLogger("rootly_rundeck_o11")
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        _handler = logging.StreamHandler()
        _formatter = logging.Formatter("%(message)s")
        _handler.setFormatter(_formatter)
        _logger.addHandler(_handler)

    @staticmethod
    def _emit(level: str, message: str, **kw):
        entry = {"level": level, "ts": datetime.datetime.utcnow().isoformat(), "msg": message}
        for k in list(kw.keys()):
            if any(s in k.lower() for s in ["token", "secret", "authorization", "auth", "password", "apikey", "api_key"]):
                kw[k] = "***redacted***"
        entry.update(kw)
        Log._logger.info(json.dumps(entry))

    @staticmethod
    def info(msg: str, **kw): Log._emit("INFO", msg, **kw)
    @staticmethod
    def warn(msg: str, **kw): Log._emit("WARN", msg, **kw)
    @staticmethod
    def error(msg: str, **kw): Log._emit("ERROR", msg, **kw)
    @staticmethod
    def debug(msg: str, **kw): Log._emit("DEBUG", msg, **kw)


# =========================
# Optional AppConfig
# =========================
_APPCONFIG_CACHE: Dict[str, Any] = {"exp": 0, "payload": None}
_APPCONFIG_SESSION_TOKEN: Optional[str] = None

def _bytes_from_configuration(cfg) -> bytes:
    if cfg is None:
        return b""
    if isinstance(cfg, (bytes, bytearray)):
        return bytes(cfg)
    if hasattr(cfg, "read"):
        return cfg.read()
    if isinstance(cfg, str):
        return cfg.encode("utf-8")
    return bytes(cfg)

def _appconfig_start_session() -> str:
    c = boto3.client("appconfigdata")
    resp = c.start_configuration_session(
        ApplicationIdentifier=Config.APPCONFIG_APP_ID,
        EnvironmentIdentifier=Config.APPCONFIG_ENV_ID,
        ConfigurationProfileIdentifier=Config.APPCONFIG_PROFILE_ID
    )
    return resp["InitialConfigurationToken"]

def _appconfig_get_latest(token: str) -> tuple[str, bytes]:
    c = boto3.client("appconfigdata")
    resp = c.get_latest_configuration(ConfigurationToken=token)
    nxt = resp.get("NextPollConfigurationToken") or token
    blob = _bytes_from_configuration(resp.get("Configuration"))
    return nxt, blob

def _normalize_keys(d: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in (d or {}).items():
        nk = re.sub(r'[^a-z0-9]+', '_', (k or '').strip().lower()).strip('_')
        out[nk] = str(v)
    return out

def apply_appconfig_overrides(force: bool = False):
    if not (Config.APPCONFIG_APP_ID and Config.APPCONFIG_ENV_ID and Config.APPCONFIG_PROFILE_ID):
        Log.info("AppConfig not configured; using in-code defaults")
        return

    now = time.time()
    if not force and _APPCONFIG_CACHE["payload"] and _APPCONFIG_CACHE["exp"] > now:
        return

    global _APPCONFIG_SESSION_TOKEN
    if not _APPCONFIG_SESSION_TOKEN:
        _APPCONFIG_SESSION_TOKEN = _appconfig_start_session()

    _APPCONFIG_SESSION_TOKEN, blob = _appconfig_get_latest(_APPCONFIG_SESSION_TOKEN)
    if not blob:
        Log.warn("AppConfig returned empty configuration; keeping existing config")
        return

    try:
        payload = json.loads(blob.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"AppConfig JSON parse error: {e}")

    rd = payload.get("rundeck") or {}
    if rd.get("url"):     Config.RUNDECK_URL = str(rd["url"])
    if rd.get("project"): Config.RUNDECK_PROJECT = str(rd["project"])

    jobs = payload.get("jobs") or {}
    remediation = jobs.get("remediation") or {}
    diagnosis = jobs.get("diagnosis") or {}
    watch_to_diag = jobs.get("sloToDiagnosis") or {}
    option_map = payload.get("optionMap") or {}
    required = payload.get("autoRequiredOptions") or []
    pass_all = bool(payload.get("passAllCustomFields", Config.PASS_ALL_CUSTOM_FIELDS))

    if remediation:      Config.REMEDIATION_JOB_ID_MAP = _normalize_keys(remediation)
    if diagnosis:        Config.DIAGNOSIS_JOB_ID_MAP   = _normalize_keys(diagnosis)
    if watch_to_diag:    Config.WATCH_TO_DIAG_MAP      = _normalize_keys(watch_to_diag)
    if option_map:       Config.RUNDECK_OPTION_MAP     = dict(option_map)

    Config.REQUIRED_AUTO_DIAGNOSIS_OPTIONS = list(required) or Config.REQUIRED_AUTO_DIAGNOSIS_OPTIONS
    Config.PASS_ALL_CUSTOM_FIELDS = pass_all

    _APPCONFIG_CACHE["payload"] = payload
    _APPCONFIG_CACHE["exp"] = now + max(10, Config.APPCONFIG_CACHE_SECONDS)

    Log.info("AppConfig applied (O11)",
            remediation=len(Config.REMEDIATION_JOB_ID_MAP),
            diag=len(Config.DIAGNOSIS_JOB_ID_MAP),
            watch=len(Config.WATCH_TO_DIAG_MAP),
            options_diag=len({**Config.DIAGNOSIS_DEFAULT_OPTION_MAP, **Config.RUNDECK_OPTION_MAP}),
            options_rem=len({**Config.REMEDIATION_DEFAULT_OPTION_MAP, **Config.RUNDECK_OPTION_MAP}),
            auto_required=len(Config.REQUIRED_AUTO_DIAGNOSIS_OPTIONS),
            pass_all=Config.PASS_ALL_CUSTOM_FIELDS)


# =========================
# Rootly Client
# =========================
class RootlyClient:
    def __init__(self):
        if not Config.ROOTLY_API_TOKEN:
            Log.warn("ROOTLY_API_TOKEN missing (requests may fail)")
        self.base = Config.ROOTLY_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {Config.ROOTLY_API_TOKEN}",
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }

    def request(self, method: str, path: str, max_retries: int = 3, **k) -> requests.Response:
        url = f"{self.base}{path}"
        k.setdefault("timeout", Config.TIMEOUT)
        Log.info("Rootly request begin", method=method, path=path)
        for attempt in range(max_retries):
            try:
                r = requests.request(method, url, headers=self.headers, **k)
                Log.info("Rootly response", path=path, status=r.status_code, attempt=attempt+1)
                if r.status_code >= 500 and attempt < (max_retries - 1):
                    Log.warn("Rootly 5xx, retrying", path=path, code=r.status_code, attempt=attempt+1)
                    time.sleep(2 ** attempt)
                    continue
                return r
            except requests.RequestException as e:
                Log.warn("Rootly request exception, retrying", path=path, err=str(e), attempt=attempt+1)
                if attempt == max_retries - 1:
                    Log.error("Rootly request failed after retries", path=path, err=str(e))
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Unreachable")

    def post_incident_event(self, incident_id: str, message: str):
        path = f"/v1/incidents/{incident_id}/events"
        payload = {"data": {"type": "incident_events",
                            "attributes": {"event": message, "visibility": "internal"}}}
        try:
            Log.info("Posting incident event", incident_id=incident_id, size=len(message))
            r = self.request("POST", path, json=payload)
            r.raise_for_status()
            Log.info("Incident event posted", incident_id=incident_id, status=r.status_code)
        except Exception as e:
            Log.warn("Failed to post incident event", incident_id=incident_id, err=str(e))

    def discover_field_id_by_name(self, field_name: str) -> str:
        q = f"/v1/form_fields?filter[name]={requests.utils.quote(field_name)}&filter[targetable_type]=Incident"
        Log.info("Discovering field id by name", field_name=field_name)
        try:
            r = self.request("GET", q)
            if r.status_code == 200:
                data = (r.json() or {}).get("data") or []
                fid = (data[0] or {}).get("id") or "" if data else ""
                Log.info("Field id discovery result", field_name=field_name, field_id=fid or "(none)")
                return fid
        except Exception as e:
            Log.warn("Mirror field discovery error", err=str(e))
        return ""

    def get_field_slug(self, field_id: str) -> str:
        if Config.MIRROR_FIELD_SLUG:
            return Config.MIRROR_FIELD_SLUG
        Log.info("Fetching field slug", field_id=field_id)
        try:
            r = self.request("GET", f"/v1/form_fields/{field_id}?fields[form_fields]=slug,name")
            if r.status_code // 100 == 2:
                slug = ((r.json() or {}).get("data") or {}).get("attributes", {}).get("slug") or ""
                Log.info("Field slug fetched", field_id=field_id, slug=slug or "(none)")
                return slug
        except Exception as e:
            Log.warn("Field slug discovery error", err=str(e))
        return ""

    def list_incident_field_selections(self, incident_id: str, field_id: str) -> Optional[str]:
        Log.info("Listing incident field selections", incident_id=incident_id, field_id=field_id)
        qs = (
            f"/v1/incidents/{incident_id}/form_field_selections"
            f"?filter[form_field_id]={field_id}"
            f"&page[size]=50"
            f"&fields[incident_form_field_selections]=id,attributes"
        )
        try:
            r = self.request("GET", qs)
            if r.status_code // 100 == 2:
                data = (r.json() or {}).get("data") or []
                for item in data:
                    attrs = (item or {}).get("attributes", {})
                    sel_id = (item or {}).get("id") or ""
                    ffid = attrs.get("form_field_id") or ""
                    if ffid == field_id:
                        Log.info("Selection found", selection_id=sel_id)
                        return sel_id
                Log.info("No selection for field", field_id=field_id)
                return ""
            Log.warn("List selections non-2xx", code=r.status_code, body=(r.text or "")[:300])
        except Exception as e:
            Log.warn("List selections error", err=str(e))
        return ""

    def patch_selection_value(self, selection_id: str, value: str) -> int:
        payload = {"data": {"type": "incident_form_field_selections",
                            "id": selection_id,
                            "attributes": {"value": value}}}
        Log.info("Patching selection value", selection_id=selection_id)
        r = self.request("PATCH", f"/v1/incident_form_field_selections/{selection_id}", json=payload)
        Log.info("Patch selection response", status=r.status_code)
        return r.status_code

    def create_selection(self, incident_id: str, field_id: str, value: str) -> int:
        payload = {"data": {"type": "incident_form_field_selections",
                            "attributes": {"value": value, "form_field_id": field_id}}}
        Log.info("Creating selection", incident_id=incident_id, field_id=field_id)
        r = self.request("POST", f"/v1/incidents/{incident_id}/form_field_selections", json=payload)
        Log.info("Create selection response", status=r.status_code)
        return r.status_code

    def patch_incident_custom_fields(self, incident_id: str, slug: str, value: str) -> int:
        if not slug:
            Log.warn("patch_incident_custom_fields called with empty slug")
            return 0
        payload = {"data": {"type": "incidents", "id": incident_id,
                            "attributes": {"custom_fields": {slug: value}}}}
        Log.info("Patching incident custom_fields (fallback)", incident_id=incident_id, slug=slug)
        r = self.request("PATCH", f"/v1/incidents/{incident_id}", json=payload)
        Log.info("Patch incident custom_fields response", status=r.status_code)
        return r.status_code


# =========================
# Rundeck Client & Errors
# =========================
class RundeckStartError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Rundeck start error {status_code}: {body[:300]}")


class RundeckClient:
    def __init__(self):
        if not Config.RUNDECK_API_TOKEN:
            Log.warn("RUNDECK_API_TOKEN_Community missing (requests may fail)")
        self.base = Config.RUNDECK_URL
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Rundeck-Auth-Token": Config.RUNDECK_API_TOKEN,
            "Rundeck-GitHub-Action": Config.GITHUB_ACTION_ID,
        }

    def start_job(self, job_id: str, options: Dict[str, str]) -> str:
        url = f"{self.base}/job/{job_id}/run"
        payload = {"project": Config.RUNDECK_PROJECT, "options": options}
        Log.info("Rundeck start_job begin", url=url, job_id=job_id, project=Config.RUNDECK_PROJECT, options=options)
        
        # Make the request
        r = requests.post(url, headers=self.headers, json=payload, timeout=Config.TIMEOUT)
        
        # CRITICAL FIX: Save response text IMMEDIATELY
        response_text = r.text
        
        Log.info("Rundeck start_job response", status=r.status_code, ok=r.ok)
        
        try:
            r.raise_for_status()
        except requests.HTTPError:
            # Use saved response_text instead of r.text
            Log.error("Rundeck start_job HTTPError", status=r.status_code, body=(response_text or "")[:800])
            raise RundeckStartError(r.status_code, (response_text or ""))

        # Parse from saved text instead of calling r.json()
        try:
            data = json.loads(response_text) or {}
        except json.JSONDecodeError as e:
            Log.error("Rundeck response JSON parse error", error=str(e), preview=response_text[:200])
            raise RundeckStartError(502, f"Invalid JSON response: {str(e)}")
        
        exec_id = str(data.get("id") or "")
        Log.info("Rundeck execution id parsed", execution_id=exec_id or "(empty)")
        if not exec_id:
            raise RundeckStartError(502, "Rundeck start succeeded but no execution id in response")
        return exec_id

    def poll_until_done(self, execution_id: str) -> Dict[str, Any]:
        url = f"{self.base}/execution/{execution_id}/state"
        Log.info("Rundeck polling begin", execution_id=execution_id, url=url,
                max_retries=Config.MAX_RETRIES, interval=Config.POLLING_INTERVAL)
        for attempt in range(Config.MAX_RETRIES):
            r = requests.get(url, headers=self.headers, timeout=Config.TIMEOUT)
            Log.info("Rundeck poll tick", attempt=attempt+1, status=r.status_code)
            r.raise_for_status()
            data = r.json()
            if data.get("completed"):
                Log.info("Rundeck poll complete", execution_id=execution_id, final_state=data.get("executionState"))
                return data
            if attempt == Config.MAX_RETRIES - 1:
                Log.error("Rundeck poll timeout", execution_id=execution_id)
                raise TimeoutError(f"Rundeck execution {execution_id} not complete within timeout")
            time.sleep(Config.POLLING_INTERVAL)
        return {}

    def fetch_output(self, execution_id: str) -> str:
        url = f"{self.base}/execution/{execution_id}/output"
        Log.info("Fetching Rundeck output", execution_id=execution_id, url=url)
        r = requests.get(url, headers=self.headers, timeout=Config.TIMEOUT)
        Log.info("Rundeck output response", status=r.status_code)
        r.raise_for_status()
        try:
            j = r.json() or {}
            entries = j.get("entries", []) or []
        except ValueError:
            Log.warn("Rundeck output non-JSON; returning raw text", size=len(r.text or ""))
            return (r.text or "").strip()[:8000]
        keep: List[str] = []

        section: List[str] = []
        in_kv = False
        in_value = False

        def flush_section():
            if section:
                keep.extend(section)
                keep.append("")

        for e in entries:
            raw = (e or {}).get("log", "")
            line = re.sub(r'^\d{2}:\d{2}:\d{2}\s+', '', raw)
            line = _clean_line(line)
            if not line.strip():
                continue

            # horizontal rule between blocks
            if re.match(r'-{3,}$', line.strip()):
                if in_kv:
                    in_kv = False
                    in_value = False
                flush_section()
                section = []
                continue
            if "key value data: results" in line.lower():
                Log.info("KV table detected in Rundeck output — keeping only VALUE column and discarding pre-table text")
                keep = []
                section = []
                in_kv = True
                in_value = False
                continue

            hdr = line.strip().lower()
            if in_kv and hdr == "key":
                # ignore header cell
                continue
            if in_kv and hdr == "value":
                in_value = True
                continue
            if in_kv:
                if in_value:
                    parts = re.split(r'\s{2,}', line)
                    if parts:
                        val_text = parts[-1]
                        if val_text.strip():
                            section.append(val_text)
                continue
            section.append(line)

        flush_section()
        deduped: List[str] = []
        for s in keep:
            if not deduped or s != deduped[-1]:
                deduped.append(s)
        out = "\n".join(deduped).replace("\r\n", "\n").strip()
        out = re.sub(r'\n[ \t]*\n+', '\n\n', out)
        blocks = [b.strip() for b in re.split(r'\n\n+', out) if b.strip()]
        seen, uniq = set(), []
        for b in blocks:
            key = re.sub(r'\s+', ' ', b.lower().strip())
            if key not in seen:
                seen.add(key)
                uniq.append(b)

        out = "\n\n".join(uniq)
        # -----------------------------------------------------------------

        # === Section-aware de-dupe + group separators ===
        SECTION_START = re.compile(
            r'^(?:'
            r'Cloud Account ID:|'
            r'Cloud Region:|'
            r'Frontends of the environment:|'
            r'Database of the environment:|'
            r'Details for [^\n]+'
            r')\s*$',
            re.IGNORECASE
        )

        # 1) Split output into sections at known headers
        lines = out.split("\n")
        sections, cur = [], []
        for ln in lines:
            if SECTION_START.match(ln.strip()):
                if cur:
                    sections.append("\n".join(cur).strip())
                    cur = []
            cur.append(ln)
        if cur:
            sections.append("\n".join(cur).strip())

        # 2) Keep only the first occurrence of each section (by normalized first line)
        seen_headers, uniq_sections = set(), []
        for sec in sections:
            first_line = sec.split("\n", 1)[0]
            first_line_norm = re.sub(r'\s+', ' ', first_line.strip().lower())
            if first_line_norm in seen_headers:
                continue
            seen_headers.add(first_line_norm)
            uniq_sections.append(sec)

        # 3) Classify sections into the four visual groups we want
        def classify(header: str) -> str:
            h = header.strip().lower()
            if h.startswith("cloud account id:") or h.startswith("cloud region:"):
                return "acct"
            if h.startswith("frontends of the environment:"):
                return "fe"
            # IIS app-pools section has a 15m/1m window in its header
            if h.startswith("details for") and ("last 15m" in h or "bucket aggregation of 1m" in h):
                return "iis"
            # Frontend metrics (20m/24h windows)
            if h.startswith("details for") and ("2m" in h or "30m" in h):
                return "fe"
            if h.startswith("database of the environment:") or h.startswith("details for db"):
                return "db"
            return "misc"

        groups = {"acct": [], "fe": [], "iis": [], "db": [], "misc": []}
        for sec in uniq_sections:
            header = sec.split("\n", 1)[0]
            groups[classify(header)].append(sec)

        def join_group(xs: list[str]) -> str:
            return "\n\n".join(xs).strip()

        # 4) Render groups with a separator line between them
        SEP = "\n\n-----------------------\n\n"
        ordered_text_blocks = []
        for key in ("acct", "fe", "iis", "db"):
            if groups[key]:
                ordered_text_blocks.append(join_group(groups[key]))
        if groups["misc"]:
            ordered_text_blocks.append(join_group(groups["misc"]))

        out = SEP.join(ordered_text_blocks).strip()

        Log.info("Section de-dupe", sections_before=len(sections), sections_after=len(uniq_sections))
        # === end section-aware de-dupe + group separators ===

        Log.info("Rundeck output parsed", lines=len(deduped), size=len(out))
        return out
# =========================
# DynamoDB helpers (short-window dedupe)
# =========================
class DDB:
    def __init__(self):
        self.c = boto3.client("dynamodb")
        self.table = Config.DDB_TABLE

    def acquire_rem_guard(self, incident_id: str, job_key: str, ttl_seconds: Optional[int] = None) -> bool:
        now = int(time.time())
        ttl_s = ttl_seconds if ttl_seconds is not None else Config.REM_GUARD_TTL
        ttl = now + ttl_s
        cutoff = now - ttl_s
        pk = f"rem_guard#{incident_id}#{job_key or 'nokey'}"
        try:
            self.c.put_item(
                TableName=self.table,
                Item={'incident_id': {'S': pk}, 'ts': {'N': str(now)}, 'ttl': {'N': str(ttl)}},
                ConditionExpression="attribute_not_exists(incident_id)"
            )
            Log.info("Rem guard created", pk=pk)
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') != 'ConditionalCheckFailedException':
                Log.warn("Rem guard put error", err=str(e))
                return True if Config.FAIL_OPEN_ON_DDB_ERROR else False
        try:
            self.c.update_item(
                TableName=self.table,
                Key={'incident_id': {'S': pk}},
                UpdateExpression="SET #ts = :now, #ttl = :ttl",
                ConditionExpression="attribute_not_exists(#ts) OR #ts < :cutoff",
                ExpressionAttributeNames={'#ts': 'ts', '#ttl': 'ttl'},
                ExpressionAttributeValues={
                    ':now': {'N': str(now)}, ':ttl': {'N': str(ttl)}, ':cutoff': {'N': str(cutoff)}
                },
                ReturnValues="NONE"
            )
            Log.info("Rem guard refreshed (window elapsed)", pk=pk)
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                Log.info("Rem guard hit; duplicate suppressed", pk=pk)
                return False
            Log.warn("Rem guard update error", err=str(e))
            return True if Config.FAIL_OPEN_ON_DDB_ERROR else False


# =========================
# Helpers (safe parsing & normalization)
# =========================
def _extract_body(event: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(event, dict) and 'body' in event:
        b = event.get('body')
        if isinstance(b, str):
            try:
                return json.loads(b)
            except Exception as e:
                Log.warn("Body JSON parse error", err=str(e), raw_len=len(b or ""))
                return {}
        return b or {}
    return event if isinstance(event, dict) else {}


def _sanitize(s: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', s).strip("_")


def _norm_key(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', (s or '').strip().lower()).strip('_')


def normalize_custom_fields(cf_raw: Union[None, Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, str]:
    if not cf_raw:
        return {}
    if isinstance(cf_raw, dict):
        return {str(k): str(v) for k, v in cf_raw.items() if v is not None and str(v).strip() != ""}
    out: Dict[str, str] = {}
    if isinstance(cf_raw, list):
        for field in cf_raw:
            if not isinstance(field, dict):
                continue
            meta = field.get("custom_field") or {}
            slug = (meta.get("slug") or meta.get("name") or "").strip()
            if not slug:
                continue
            val = None
            sel = field.get("selected_options")
            if isinstance(sel, list) and sel:
                opt = sel[0] or {}
                for k in ("value", "slug", "name", "label", "text"):
                    if opt.get(k):
                        val = opt[k]
                        break
            if val is None:
                val = field.get("value")
            if val is not None and str(val).strip() != "":
                out[slug] = str(val).strip()
    return out


def _cf_value_from_root(obj: Dict[str, Any], slug_like: str) -> Any:
    data = (obj or {}).get("data") or {}
    cf_map = normalize_custom_fields(data.get("custom_fields"))
    if not slug_like:
        return None
    want = _norm_key(slug_like.replace("-", "_"))
    for k, v in cf_map.items():
        if _norm_key(k) == want:
            return v
    return None


def _get_by_path(obj: Any, path: str) -> Any:
    if not isinstance(path, str) or not path:
        return None
    parts = path.split(".")
    if len(parts) >= 3 and parts[0] == "data" and parts[1] == "custom_fields":
        slug = ".".join(parts[2:])
        return _cf_value_from_root(obj, slug)
    cur: Any = obj
    for part in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            if part.isdigit():
                i = int(part)
                cur = cur[i] if 0 <= i < len(cur) else None
            else:
                hits: List[Any] = []
                for item in cur:
                    if isinstance(item, dict) and part in item:
                        hits.append(item.get(part))
                if not hits:
                    return None
                cur = hits[0] if len(hits) == 1 else hits
        else:
            return None
    return cur


ANSI_RE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def _try_parse_single_kv_json(s: str) -> Optional[str]:
    """
    If a line looks like {"some_key": "multi\\nline\\ntext"} (or with single quotes),
    return the unescaped string value; otherwise None.
    """
    t = s.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    try:
        obj = json.loads(t)
    except Exception:
        try:
            obj = ast.literal_eval(t)
        except Exception:
            return None
    if isinstance(obj, dict) and len(obj) == 1:
        val = next(iter(obj.values()))
        if isinstance(val, str):
            return (val
                    .replace("\\n", "\n")
                    .replace("\\t", "\t")
                    .replace('\\"', '"')
                    .strip())
    return None

def _clean_line(s: str) -> str:
    s = ANSI_RE.sub("", s).rstrip()
    pretty = _try_parse_single_kv_json(s)
    return pretty if pretty is not None else s

def classify_failure(text: str) -> str:
    t = (text or "").lower()

    if "invalid aws account id" in t:
        return "CONFIGURATION_ERROR"
    if "missing required" in t or "required option" in t:
        return "MISSING_INPUT"
    if "read timed out" in t or "connection timed out" in t:
        return "DEPENDENCY_TIMEOUT"
    if "access denied" in t or "not authorized" in t:
        return "IAM_ERROR"
    if "rundeck start error" in t:
        return "RUNDECK_API_ERROR"

    return "UNKNOWN_FAILURE"

def build_rundeck_options(rootly_body: Dict[str, Any], mode: str) -> Dict[str, str]:
    Log.info("Building Rundeck options begin", mode=mode)
    options: Dict[str, str] = {}

    # Choose base defaults by mode
    base_map = (Config.DIAGNOSIS_DEFAULT_OPTION_MAP
                if mode == "diagnosis" else
                Config.REMEDIATION_DEFAULT_OPTION_MAP)

    # AppConfig/env overrides still apply on top
    option_map = {**base_map, **Config.RUNDECK_OPTION_MAP}

    Log.info("Option map resolved",
            default_keys=list(base_map.keys()),
            override_keys=list(Config.RUNDECK_OPTION_MAP.keys()),
            mode=mode)

    for src, dest in option_map.items():
        val = _get_by_path(rootly_body, src)
        if val is not None:
            key = _sanitize(dest)
            options[key] = str(val)
            Log.info("Option mapped", source=src, dest=key, mode=mode)

    # Pass-through all custom fields if enabled (unchanged)
    if Config.PASS_ALL_CUSTOM_FIELDS:
        cf_raw = ((rootly_body.get("data") or {}).get("custom_fields"))
        cf_map = normalize_custom_fields(cf_raw)
        for slug, val in cf_map.items():
            key = f"cf_{_sanitize(slug)}"
            if key not in options:
                options[key] = str(val)
                Log.info("Option propagated from custom_fields",
                        slug=slug, dest=key, value_preview=str(val)[:120], mode=mode)

    Log.info("Building Rundeck options done", count=len(options), mode=mode)
    return options


def format_for_rootly(cleaned: str, kind: str, auto: bool = False, selector: str = "") -> str:
    title = "🚀 Diagnosis / 🛠️ Remediation Job Results" 
    if auto:
        title = f"{title} (auto)"
    header = f"*{title}*"
    pretty = (cleaned or "").strip() or "(no output)"
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    sel = f"\n_Selector: {selector}_" if selector else ""
    return f"{header}{sel}\n\n```\n{pretty}\n```\n\n_Processed at {ts}_\n"


def format_error_for_rootly(kind: str, details: str, auto: bool = False, selector: str = "") -> str:
    """lambd-2 variant: user-facing guidance + error details in code block (no ROUTING:: category)."""
    title = "🚨 Diagnosis / Remediation  Job Failed" 
    if auto:
        title = f"{title} (auto)"
    guidance = (
        "Rundeck rejected the request (likely a *required option is missing*). "
        "For diagnosis ensure env_orn is set. "
        "For remediation, fill cloud_account, region, and instance_id via the O11 form."
    )
    details_str = (details or "").strip()
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    sel = f"\n_Selector: {selector}_" if selector else ""
    body = f"*{title}*{sel}\n\n{guidance}\n\n```\n{details_str[:6000]}\n```\n\n_Processed at {ts}_\n"
    return body


def _new_token(suffix: str = "") -> str:
    core = f"{int(time.time()*1000)}_{os.urandom(2).hex()}"
    return f"{Config.MIRROR_TOKEN_PREFIX}_{core}{('_' + suffix) if suffix else ''}"


def set_mirror_ready_token(rootly: RootlyClient, incident_id: str, exec_id: str = "") -> bool:
    Log.info("Setting mirror ready token begin", incident_id=incident_id, exec_suffix=(exec_id or "")[:24])
    field_id = Config.MIRROR_FIELD_ID or rootly.discover_field_id_by_name(Config.MIRROR_FIELD_NAME)
    if not field_id:
        rootly.post_incident_event(incident_id, ":warning: Mirror token aborted: custom field id could not be determined.")
        Log.warn("Mirror field id missing; aborting")
        return False

    token = _new_token(exec_id)
    Log.info("Mirror token generated", length=len(token))

    try:
        sel_id = rootly.list_incident_field_selections(incident_id, field_id)
        if sel_id:
            st = rootly.patch_selection_value(sel_id, token)
            Log.info("Selection PATCH", status=st, selection_id=sel_id)
            ok = 200 <= st < 300
        else:
            stc = rootly.create_selection(incident_id, field_id, token)
            Log.info("Selection CREATE (no existing)", status=stc)
            ok = 200 <= stc < 300

        if ok:
            Log.info("Mirror token write completed (selection)")
            return True

        slug = rootly.get_field_slug(field_id)
        if slug:
            st2 = rootly.patch_incident_custom_fields(incident_id, slug, token)
            Log.info("Fallback custom_fields PATCH", status=st2, slug=slug)
            return 200 <= st2 < 300

        Log.warn("Mirror token fallback skipped; slug not available")
        return False

    except Exception as e:
        Log.warn("Mirror token write error", err=str(e))
        rootly.post_incident_event(incident_id, f":warning: Mirror token write error: {e}")
        return False


# =========================
# Timeline Note Dedupe Helper
# =========================
def post_incident_event_once(rootly: RootlyClient, ddb: DDB, incident_id: str, guard_key: str, message: str,
                            ttl_seconds: Optional[int] = None) -> bool:
    key = f"note:{guard_key}"
    if ddb.acquire_rem_guard(incident_id, key, ttl_seconds=ttl_seconds):
        rootly.post_incident_event(incident_id, message)
        return True
    Log.info("Note suppressed by rem guard", pk=key)
    return False

def _has(obj: Dict[str, Any], path: str) -> bool:
    return _get_by_path(obj, path) is not None


def validate_payload(body: Dict[str, Any]) -> Optional[str]:
    if not _has(body, "data.id"):
        return "missing data.id"
    return None


# =========================
# poll.rundeck handler
# =========================
def handle_poll_rundeck_event(body: Dict[str, Any]) -> Dict[str, Any]:
    rootly = RootlyClient()
    rundeck = RundeckClient()
    ddb = DDB()

    data = body.get("data") or {}
    incident_id = (data.get("id") or "").strip()
    exec_id = (data.get("execution_id") or "").strip()
    mode = (data.get("mode") or "diagnosis").strip() or "diagnosis"
    selector = (data.get("selector") or "").strip()

    if not incident_id or not exec_id:
        Log.warn("poll.rundeck missing inputs", incident_id=incident_id, exec_id=exec_id)
        return _response(200, "ignored_poll_missing_inputs")

    try:
        rundeck.poll_until_done(exec_id)
        raw = rundeck.fetch_output(exec_id)
        formatted = format_for_rootly(raw, mode, auto=("auto:" in selector), selector=selector)
        rootly.post_incident_event(incident_id, formatted)

        if ddb.acquire_rem_guard(incident_id, f"mirror:poll:{exec_id}", ttl_seconds=Config.MIRROR_DEDUPE_TTL):
            set_mirror_ready_token(rootly, incident_id, str(exec_id))

        return _response(200, "poll_posted", incident_id=incident_id, execution_id=str(exec_id), mode=mode)
    except Exception as e:
        Log.error("poll.rundeck failed", err=str(e), exec_id=exec_id, incident_id=incident_id)
        formatted = format_error_for_rootly(mode, str(e), auto=("auto:" in selector), selector=selector)
        post_incident_event_once(rootly, ddb, incident_id, "poll_error", formatted,
                                ttl_seconds=Config.AUTO_DEDUPE_TTL)
        failure_category = classify_failure(str(e))
        rootly.post_incident_event(
            incident_id,
            f"ROUTING::{failure_category}"
        )
        guard = f"mirror:poll_err:{mode}:{selector or exec_id or 'poll'}"
        if ddb.acquire_rem_guard(incident_id, guard, ttl_seconds=Config.MIRROR_DEDUPE_TTL):
            set_mirror_ready_token(rootly, incident_id, f"poll_error_{mode}")
        return _response(200, "poll_failed_but_mirrored", incident_id=incident_id, error=str(e), mode=mode)


# =========================
# Lambda handler
# =========================
def _response(code: int, status: str, **k):
    Log.info("Responding", status_code=code, status=status, extra=k)
    return {"statusCode": code, "body": json.dumps({"status": status, **k})}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    Log.info("Lambda invoked", has_body=('body' in (event or {})))

    # AppConfig overrides (if configured)
    try:
        apply_appconfig_overrides()
    except Exception as e:
        Log.warn("AppConfig override failed; continuing with in-code defaults", err=str(e))

    Log.info("Env summary (O11)",
            rundeck_url=Config.RUNDECK_URL,
            rundeck_project=Config.RUNDECK_PROJECT,
            ddb_table=Config.DDB_TABLE,
            pass_all_custom_fields=Config.PASS_ALL_CUSTOM_FIELDS,
            has_lambda_fn=bool(Config.LAMBDA_FUNCTION_NAME))

    try:
        rootly = RootlyClient()
        rundeck = RundeckClient()
        ddb = DDB()

        body = _extract_body(event)
        if not body:
            Log.warn("Empty body; nothing to do")
            return _response(200, "ignored_empty_body")

        err = validate_payload(body) if (body.get("event") or {}).get("type") != "poll.rundeck" else None
        if err:
            Log.warn("Payload validation failed", reason=err)
            return _response(200, "ignored_invalid_payload", reason=err)

        Log.info("Parsed body", len=len(json.dumps(body)) if body else 0)

        evt_type = ((body.get('event') or {}).get('type')) or ""
        data = body.get('data') or {}
        incident_id = (data.get('id') or "").strip()
        title = data.get('title', '').strip()
        cf_map = normalize_custom_fields(data.get('custom_fields'))

        if not incident_id and evt_type != "poll.rundeck":
            Log.warn("Missing incident id; ignoring")
            return _response(200, "ignored_missing_incident_id")

        Log.info("Event envelope", evt_type=evt_type or "(none)", incident_id=incident_id or "(none)")

        if evt_type == "poll.rundeck":
            return handle_poll_rundeck_event(body)

        auto = False
        selector = ""
        job_id = ""
        mode = ""

        # Auto diagnosis routing based on watch_id
        watch_raw = (cf_map.get('watch_id') or '').strip()
        watch_key = _norm_key(watch_raw) if watch_raw else ""

        # Manual remediation selection
        manual_key_raw = (cf_map.get('o11_remediation_job')
                or cf_map.get('o11_diagnosis_job')
                or '').strip()
        manual_key = _norm_key(manual_key_raw) if manual_key_raw else ""

        if evt_type in ("incident.created", "auto.diagnosis"):
            if watch_key and watch_key in Config.WATCH_TO_DIAG_MAP:
                if not ddb.acquire_rem_guard(incident_id, f"gate:auto:{watch_key}", ttl_seconds=Config.AUTO_DEDUPE_TTL):
                    return _response(200, "auto_already_processed_recently", incident_id=incident_id)

                job_id = Config.WATCH_TO_DIAG_MAP[watch_key]
                mode = "diagnosis"
                auto = True
                selector = f"auto:watch:{watch_key}"
                Log.info("Auto diagnosis selected", watch_id=watch_key, job_id=job_id)
            else:
                Log.info("Auto diagnosis skipped (unknown or missing watch_id)", watch_id=watch_key or "(none)")
                msg = (
                    f"Unrecognized or missing `watch_id` for auto diagnosis. "
                    f"Received: '{watch_key or '(none)'}'. "
                    "You can run a remediation manually via **Trigger O11 Rundeck Job** after filling required inputs."
                )
                formatted = format_error_for_rootly("diagnosis", msg, auto=True,
                                                    selector=f"auto:watch:{watch_key or 'none'}")

                post_incident_event_once(rootly, ddb, incident_id, "auto_skip_unknown_watch", formatted,
                                        ttl_seconds=Config.AUTO_DEDUPE_TTL)

                if ddb.acquire_rem_guard(incident_id, "mirror:auto_skip_unknown_watch",
                                        ttl_seconds=Config.MIRROR_DEDUPE_TTL):
                    set_mirror_ready_token(rootly, incident_id, "auto_skip_unknown_watch")

                return _response(200, "auto_skip_unknown_watch", incident_id=incident_id, watch_id=watch_key or "(none)")

        elif evt_type == "workflow.run":
            Log.info("Manual job selection parsed", raw=manual_key_raw, normalized=manual_key)
            if not manual_key:
                Log.info("Missing O11 Remediation Job key; ignoring cleanly", incident_id=incident_id)
                return _response(200, "ignored_empty_or_missing", incident_id=incident_id)

            if manual_key in Config.REMEDIATION_JOB_ID_MAP:
                mode = "remediation"
                job_id = Config.REMEDIATION_JOB_ID_MAP[manual_key]
            elif manual_key in Config.DIAGNOSIS_JOB_ID_MAP:
                mode = "diagnosis"
                job_id = Config.DIAGNOSIS_JOB_ID_MAP[manual_key]
            else:
                msg = f"Unknown O11 Remediation Job selection '{manual_key}'."
                Log.warn("Job key not found", key=manual_key)
                formatted = format_error_for_rootly("diagnosis", msg)
                post_incident_event_once(rootly, ddb, incident_id, "unknown_job_key", formatted,
                                        ttl_seconds=Config.AUTO_DEDUPE_TTL)

                if ddb.acquire_rem_guard(incident_id, "mirror:unknown_job",
                                        ttl_seconds=Config.MIRROR_DEDUPE_TTL):
                    set_mirror_ready_token(rootly, incident_id, "unknown_job")

                return _response(200, "job_not_found_but_mirrored", incident_id=incident_id, job_key=manual_key)

            selector = f"manual:{mode}:{manual_key}"
            Log.info("Manual job identity resolved", mode=mode, job_id=job_id, selector=selector)

        else:
            Log.info("Ignored event", evt_type=evt_type or "(none)")
            return _response(200, "ignored_event", event_type=evt_type or "(none)")

        if not job_id:
            Log.warn("No job_id after routing", evt_type=evt_type, watch_id=watch_key, manual_key=manual_key)
            return _response(200, "no_job_routed", incident_id=incident_id)

        guard_key = selector or f"{mode}:{manual_key or watch_key or 'unknown'}"
        if not ddb.acquire_rem_guard(incident_id, guard_key, ttl_seconds=Config.AUTO_DEDUPE_TTL if auto else None):
            return _response(200, "ignored_duplicate", incident_id=incident_id, guard_key=guard_key, mode=mode)

        # Build options
        try:
            options = build_rundeck_options(body, mode)
        except Exception as e:
            Log.error("build_rundeck_options error", err=str(e))
            formatted = format_error_for_rootly(mode or "diagnosis", f"options build failure: {e}",
                                                auto=auto, selector=selector)
            post_incident_event_once(rootly, ddb, incident_id, "options_build_error", formatted,
                                    ttl_seconds=Config.AUTO_DEDUPE_TTL if auto else None)
            if ddb.acquire_rem_guard(incident_id, "mirror:options_build_error",
                                    ttl_seconds=Config.MIRROR_DEDUPE_TTL):
                set_mirror_ready_token(rootly, incident_id, "options_build_error")
            return _response(200, "options_build_error", incident_id=incident_id, mode=mode or "diagnosis")

        Log.info("Rundeck options built",
            count=len(options),
            keys_sorted=sorted(options.keys()))

        # Auto diagnosis preflight
        if auto and mode == "diagnosis":
            missing = [k for k in Config.REQUIRED_AUTO_DIAGNOSIS_OPTIONS if not str(options.get(k, "")).strip()]
            if missing:
                guidance = f"Missing required options for auto diagnosis: {', '.join(missing)}"
                Log.warn("Preflight missing options", mode=mode, missing=missing, selector=selector)
                formatted = format_error_for_rootly(mode, guidance, auto=auto, selector=selector)
                post_incident_event_once(rootly, ddb, incident_id, "preflight_missing_options", formatted,
                                        ttl_seconds=Config.AUTO_DEDUPE_TTL)
                pre_key = f"mirror:preflight:{mode}:{selector or '_'}:{'_'.join(missing)}"
                if ddb.acquire_rem_guard(incident_id, pre_key, ttl_seconds=Config.MIRROR_DEDUPE_TTL):
                    set_mirror_ready_token(rootly, incident_id, f"preflight_missing_{mode}_{'_'.join(missing)}")
                return _response(200, "preflight_validation_error", incident_id=incident_id, mode=mode, missing=missing)

        # Start Rundeck
        try:
            exec_id = rundeck.start_job(job_id, options)
            Log.info("Rundeck execution started", execution_id=str(exec_id), mode=mode, selector=selector)
            if not Config.LAMBDA_FUNCTION_NAME:
                Log.warn("LAMBDA_FUNCTION_NAME not set; performing inline poll (blocking)")
                try:
                    # Poll ONCE
                    state = rundeck.poll_until_done(exec_id)
                    execution_state = (state.get("executionState") or "").lower()

                    # Hard fail if job failed
                    if execution_state != "succeeded":
                        raise RuntimeError(f"RUNDECK_EXECUTION_FAILED::{execution_state}")

                    # Fetch output ONLY on success
                    raw = rundeck.fetch_output(exec_id)
                    formatted = format_for_rootly(
                        raw,
                        mode,
                        auto=("auto:" in selector),
                        selector=selector
                    )
                    rootly.post_incident_event(incident_id, formatted)

                    if ddb.acquire_rem_guard(
                        incident_id,
                        f"mirror:inline:{exec_id}",
                        ttl_seconds=Config.MIRROR_DEDUPE_TTL
                    ):
                        set_mirror_ready_token(rootly, incident_id, str(exec_id))

                    return _response(200, f"{mode}_posted", incident_id=incident_id)

                except Exception as e:
                    Log.error("Inline poll/post error", err=str(e), selector=selector)

                    formatted = format_error_for_rootly(
                        mode,
                        str(e),
                        auto=auto,
                        selector=selector
                    )

                    post_incident_event_once(
                        rootly,
                        ddb,
                        incident_id,
                        "inline_poll_error",
                        formatted,
                        ttl_seconds=Config.AUTO_DEDUPE_TTL
                    )

                    failure_category = classify_failure(str(e))
                    rootly.post_incident_event(
                        incident_id,
                        f"ROUTING::{failure_category}"
                    )

                    inline_key = f"mirror:inline_err:{mode}:{selector or exec_id or 'inline'}"
                    if ddb.acquire_rem_guard(
                        incident_id,
                        inline_key,
                        ttl_seconds=Config.MIRROR_DEDUPE_TTL
                    ):
                        set_mirror_ready_token(rootly, incident_id, f"inline_poll_error_{mode}")

                    return _response(
                        200,
                        "poll_failed_but_mirrored",
                        incident_id=incident_id,
                        error=str(e),
                        mode=mode
                    )
            else:
                try:
                    payload = {
                        "event": {"type": "poll.rundeck"},
                        "data":  {
                            "id": incident_id,
                            "title": title,
                            "execution_id": str(exec_id),
                            "mode": mode,
                            "selector": selector
                        }
                    }
                    Log.info("Invoking async poll", function=Config.LAMBDA_FUNCTION_NAME, payload_preview=str(payload)[:300])
                    boto3.client('lambda').invoke(
                        FunctionName=Config.LAMBDA_FUNCTION_NAME,
                        InvocationType="Event",
                        Payload=json.dumps(payload).encode("utf-8")
                    )
                    Log.info("Async poll invoked")
                except Exception as e:
                    Log.warn("Async poll invoke failed (non-blocking)", err=str(e))
                return _response(200, "accepted", incident_id=incident_id, execution_id=str(exec_id), mode=mode)
        except RundeckStartError as e:
            Log.error("Rundeck start failed", code=e.status_code, body=e.body[:400], selector=selector)
            guidance = e.body or f"HTTP {e.status_code}: (no body)"
            formatted = format_error_for_rootly(mode, guidance, auto=auto, selector=selector)
            post_incident_event_once(rootly, ddb, incident_id, f"rundeck_start_{e.status_code}", formatted,
                                    ttl_seconds=Config.AUTO_DEDUPE_TTL if auto else None)
            start_key = f"mirror:start:{mode}:{selector or '_'}:{e.status_code}"
            if ddb.acquire_rem_guard(incident_id, start_key, ttl_seconds=Config.MIRROR_DEDUPE_TTL):
                set_mirror_ready_token(rootly, incident_id, f"start_{mode}_{e.status_code}")
            return _response(200, "rundeck_start_validation_error", incident_id=incident_id, mode=mode)

    except Exception as e:
        Log.error("Unhandled exception", err=str(e))
        try:
            body = _extract_body(event)
            incident_id = ((body or {}).get("data") or {}).get("id") or ""
            if incident_id:
                formatted = format_error_for_rootly("diagnosis", str(e), auto=False)
                try:
                    post_incident_event_once(RootlyClient(), DDB(), incident_id, "handler_error", formatted,
                                            ttl_seconds=Config.AUTO_DEDUPE_TTL)
                except Exception:
                    RootlyClient().post_incident_event(incident_id, formatted)
                try:
                    DDB().acquire_rem_guard(incident_id, "mirror:handler_error",
                                            ttl_seconds=Config.MIRROR_DEDUPE_TTL)
                    set_mirror_ready_token(RootlyClient(), incident_id, "handler_error")
                except Exception as _e:
                    Log.warn("Mirror attempt after handler error failed", err=str(_e))
        except Exception as _e:
            Log.warn("Exception while mirroring handler error", err=str(_e))
        return _response(500, "exception", error=str(e))