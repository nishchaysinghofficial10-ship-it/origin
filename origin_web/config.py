"""Configuration with secure-by-default startup validation."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


def _positive_int(name: str, default: int, *, minimum: int = 1,
                  maximum: int = 1_000_000) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return value


def _enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "1" if default else "0")
    if raw not in ("0", "1"):
        raise ConfigError(f"{name} must be 0 or 1")
    return raw == "1"


def _model_name() -> str:
    value = os.environ.get("ORIGIN_RESEARCH_MODEL", "claude-sonnet-4-6").strip()
    if not value or len(value) > 100 or not all(
            character.isalnum() or character in "._-" for character in value):
        raise ConfigError("ORIGIN_RESEARCH_MODEL is invalid")
    return value


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _tokens_from_env() -> dict[str, str]:
    """Return digest -> non-secret principal label."""
    raw_json = os.environ.get("ORIGIN_WEB_BETA_TOKENS", "").strip()
    single = os.environ.get("ORIGIN_WEB_BETA_TOKEN", "").strip()
    token_file = os.environ.get("ORIGIN_WEB_BETA_TOKEN_FILE", "").strip()
    if token_file:
        try:
            file_token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError("ORIGIN_WEB_BETA_TOKEN_FILE could not be read") from exc
        if single and not hmac_compare(single, file_token):
            raise ConfigError("configure either a token or token file, not two different values")
        single = file_token
    records: dict[str, str] = {}
    if raw_json:
        try:
            decoded = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ConfigError("ORIGIN_WEB_BETA_TOKENS must be a JSON object") from exc
        if not isinstance(decoded, dict):
            raise ConfigError("ORIGIN_WEB_BETA_TOKENS must be a JSON object")
        for token, label in decoded.items():
            if not isinstance(token, str) or len(token) < 24:
                raise ConfigError("every beta token must be at least 24 characters")
            if not isinstance(label, str) or not label.strip() or len(label) > 80:
                raise ConfigError("every beta token needs a short principal label")
            records[token_digest(token)] = label.strip()
    if single:
        if len(single) < 24:
            raise ConfigError("ORIGIN_WEB_BETA_TOKEN must be at least 24 characters")
        records[token_digest(single)] = "beta-owner"
    return records


def hmac_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _admin_tokens_from_env() -> frozenset[str]:
    """Return digests for credentials allowed to use emergency controls."""
    single = os.environ.get("ORIGIN_WEB_ADMIN_TOKEN", "").strip()
    token_file = os.environ.get("ORIGIN_WEB_ADMIN_TOKEN_FILE", "").strip()
    if token_file:
        try:
            file_token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError("ORIGIN_WEB_ADMIN_TOKEN_FILE could not be read") from exc
        if single and not hmac_compare(single, file_token):
            raise ConfigError(
                "configure either an admin token or admin token file, not two different values")
        single = file_token
    if not single:
        return frozenset()
    if len(single) < 24:
        raise ConfigError("ORIGIN_WEB_ADMIN_TOKEN must be at least 24 characters")
    return frozenset({token_digest(single)})


@dataclass(frozen=True)
class WebConfig:
    data_dir: Path
    token_records: dict[str, str]
    admin_token_digests: frozenset[str] = field(default_factory=frozenset)
    host: str = "127.0.0.1"
    port: int = 8080
    allowed_origins: tuple[str, ...] = ()
    max_body_bytes: int = 16_384
    max_question_chars: int = 500
    requests_per_minute: int = 30
    missions_per_day: int = 5
    active_missions_per_principal: int = 1
    mission_timeout_s: int = 900
    step_timeout_s: int = 180
    worker_poll_s: float = 1.0
    environment_accepts_jobs: bool = True
    general_research_enabled: bool = False
    general_missions_per_day: int = 2
    provider_missions_per_day: int = 4
    provider_calls_per_mission: int = 1
    web_searches_per_mission: int = 3
    research_max_output_tokens: int = 3_200
    research_timeout_s: int = 120
    research_model: str = "claude-sonnet-4-6"
    anthropic_key_file: Path | None = None
    allow_insecure_local: bool = False
    public_site_url: str = "https://nishchaysinghofficial10-ship-it.github.io/origin"
    site_dir: Path | None = None
    require_tokens: bool = True
    db_path: Path = field(init=False)
    runs_dir: Path = field(init=False)

    def __post_init__(self):
        base = self.data_dir.resolve()
        object.__setattr__(self, "data_dir", base)
        object.__setattr__(self, "db_path", base / "origin_web.sqlite3")
        object.__setattr__(self, "runs_dir", base / "missions")
        if self.site_dir is not None:
            site_dir = self.site_dir.resolve()
            if not site_dir.is_dir():
                raise ConfigError("ORIGIN_WEB_SITE_DIR must be an existing directory")
            object.__setattr__(self, "site_dir", site_dir)
        if not 1 <= self.provider_calls_per_mission <= 1:
            raise ConfigError("provider calls per mission must be exactly 1")
        if not 1 <= self.web_searches_per_mission <= 5:
            raise ConfigError("web searches per mission must be between 1 and 5")
        if not 256 <= self.research_max_output_tokens <= 8_192:
            raise ConfigError("research output-token limit is invalid")
        if not 10 <= self.research_timeout_s <= 300:
            raise ConfigError("research timeout is invalid")
        if self.require_tokens and not self.token_records and not (
                self.allow_insecure_local and self.host in ("127.0.0.1", "::1", "localhost")):
            raise ConfigError(
                "no beta token configured; set ORIGIN_WEB_BETA_TOKEN or "
                "ORIGIN_WEB_BETA_TOKENS. Insecure mode is loopback-only.")
        if self.host not in ("127.0.0.1", "::1", "localhost") and self.allow_insecure_local:
            raise ConfigError("insecure mode cannot bind to a non-loopback host")
        if (self.host not in ("127.0.0.1", "::1", "localhost") and
                self.require_tokens and not self.admin_token_digests):
            raise ConfigError(
                "a separate ORIGIN_WEB_ADMIN_TOKEN is required on a public binding")
        if set(self.token_records).intersection(self.admin_token_digests):
            raise ConfigError("the beta and admin credentials must be different")
        for origin in self.allowed_origins:
            if origin in ("http://127.0.0.1:4173", "http://localhost:4173"):
                continue
            try:
                parsed = urlsplit(origin)
                port = parsed.port
            except ValueError as exc:
                raise ConfigError("allowed browser origins must be valid HTTPS origins") from exc
            if (parsed.scheme != "https" or not parsed.hostname or
                    parsed.username is not None or parsed.password is not None or
                    parsed.path or parsed.query or parsed.fragment or
                    origin != f"https://{parsed.netloc}" or
                    (port is not None and not 1 <= port <= 65_535)):
                raise ConfigError("allowed browser origins must use HTTPS")

    @classmethod
    def from_env(cls, *, require_tokens: bool = True) -> "WebConfig":
        data_dir = Path(os.environ.get("ORIGIN_WEB_DATA_DIR", "runs/web_beta"))
        origins = tuple(x.strip().rstrip("/") for x in
                        os.environ.get("ORIGIN_WEB_ALLOWED_ORIGINS", "").split(",")
                        if x.strip())
        host = os.environ.get("ORIGIN_WEB_HOST", "127.0.0.1")
        return cls(
            data_dir=data_dir,
            token_records=_tokens_from_env(),
            admin_token_digests=_admin_tokens_from_env(),
            host=host,
            port=_positive_int("ORIGIN_WEB_PORT", 8080, maximum=65_535),
            allowed_origins=origins,
            max_body_bytes=_positive_int("ORIGIN_WEB_MAX_BODY_BYTES", 16_384,
                                         maximum=1_000_000),
            max_question_chars=_positive_int("ORIGIN_WEB_MAX_QUESTION_CHARS", 500,
                                             maximum=2_000),
            requests_per_minute=_positive_int("ORIGIN_WEB_RATE_PER_MINUTE", 30,
                                              maximum=1_000),
            missions_per_day=_positive_int("ORIGIN_WEB_MISSIONS_PER_DAY", 5,
                                           maximum=100),
            active_missions_per_principal=_positive_int(
                "ORIGIN_WEB_ACTIVE_PER_PRINCIPAL", 1, maximum=10),
            mission_timeout_s=_positive_int("ORIGIN_WEB_MISSION_TIMEOUT_S", 900,
                                            maximum=86_400),
            step_timeout_s=_positive_int("ORIGIN_WEB_STEP_TIMEOUT_S", 180,
                                         maximum=3_600),
            environment_accepts_jobs=(
                os.environ.get("ORIGIN_WEB_ACCEPT_JOBS", "1") == "1"),
            general_research_enabled=_enabled(
                "ORIGIN_WEB_GENERAL_RESEARCH", False),
            general_missions_per_day=_positive_int(
                "ORIGIN_GENERAL_MISSIONS_PER_DAY", 2, maximum=20),
            provider_missions_per_day=_positive_int(
                "ORIGIN_PROVIDER_MISSIONS_PER_DAY", 4, maximum=100),
            provider_calls_per_mission=_positive_int(
                "ORIGIN_PROVIDER_CALLS_PER_MISSION", 1, maximum=1),
            web_searches_per_mission=_positive_int(
                "ORIGIN_WEB_SEARCHES_PER_MISSION", 3, maximum=5),
            research_max_output_tokens=_positive_int(
                "ORIGIN_RESEARCH_MAX_OUTPUT_TOKENS", 3_200,
                minimum=256, maximum=8_192),
            research_timeout_s=_positive_int(
                "ORIGIN_RESEARCH_TIMEOUT_S", 120, minimum=10, maximum=300),
            research_model=_model_name(),
            anthropic_key_file=(Path(value) if (value := os.environ.get(
                "ORIGIN_ANTHROPIC_KEY_FILE", "").strip()) else None),
            allow_insecure_local=(
                os.environ.get("ORIGIN_WEB_ALLOW_INSECURE_LOCAL", "0") == "1"),
            public_site_url=os.environ.get(
                "ORIGIN_WEB_PUBLIC_SITE_URL",
                "https://nishchaysinghofficial10-ship-it.github.io/origin"
            ).rstrip("/"),
            site_dir=(Path(value) if (value := os.environ.get(
                "ORIGIN_WEB_SITE_DIR", "").strip()) else None),
            require_tokens=require_tokens,
        )

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.data_dir.chmod(0o700)
            self.runs_dir.chmod(0o700)
        except OSError:
            pass
