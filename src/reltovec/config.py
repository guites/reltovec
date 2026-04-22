from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SQLiteConfig:
    path: str
    table: str
    id_column: str
    content_column: list[str]
    updated_at_column: str | None


@dataclass(frozen=True)
class BatchConfig:
    models: list[str]
    completion_window: str
    poll_interval_seconds: int
    max_batch_size: int
    api_key: str|None


@dataclass(frozen=True)
class ChromaConfig:
    host: str
    port: int
    collection_name: str


@dataclass(frozen=True)
class StateConfig:
    tracking_db_path: str


@dataclass(frozen=True)
class AppConfig:
    sqlite: SQLiteConfig
    batch: BatchConfig
    chroma: ChromaConfig
    state: StateConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    sqlite_data = _require_section(data, "sqlite")
    batch_data = _require_section(data, "batch")
    chroma_data = _require_section(data, "chroma")
    state_data = _require_section(data, "state")

    sqlite = SQLiteConfig(
        path=_require_string(sqlite_data, "path"),
        table=_require_string(sqlite_data, "table"),
        id_column=_require_string(sqlite_data, "id_column"),
        content_column=_require_string_list(sqlite_data, "content_column"),
        updated_at_column=_optional_string(sqlite_data, "updated_at_column"),
    )

    models = batch_data.get("models")
    if not isinstance(models, list) or not models:
        raise ConfigError("batch.models must be a non-empty list")
    normalized_models = [str(model).strip() for model in models if str(model).strip()]
    if not normalized_models:
        raise ConfigError("batch.models must contain at least one non-empty model name")

    batch = BatchConfig(
        models=normalized_models,
        completion_window=_require_string(batch_data, "completion_window"),
        poll_interval_seconds=_require_positive_int(
            batch_data, "poll_interval_seconds"
        ),
        max_batch_size=_require_positive_int(batch_data, "max_batch_size"),
        api_key=batch_data.get("api_key")
    )

    chroma = ChromaConfig(
        host=_require_string(chroma_data, "host"),
        port=_require_positive_int(chroma_data, "port"),
        collection_name=_require_string(chroma_data, "collection_name"),
    )

    state = StateConfig(
        tracking_db_path=_require_string(state_data, "tracking_db_path")
    )

    return AppConfig(sqlite=sqlite, batch=batch, chroma=chroma, state=state)


def _require_section(data: dict, key: str) -> dict:
    section = data.get(key)
    if not isinstance(section, dict):
        raise ConfigError(f"Missing or invalid section: [{key}]")
    return section


def _require_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_string(data: dict, key: str) -> str | None:
    if key not in data:
        return None
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string when provided")
    return value.strip()


def _require_string_list(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"{key} must be an array of non-empty strings")

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{key}[{index}] must be a non-empty string")
        normalized.append(item.strip())

    if not normalized:
        raise ConfigError(f"{key} must contain at least one column name")

    return normalized


def _require_positive_int(data: dict, key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value
