from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

import yaml
from xdg_base_dirs import xdg_cache_home, xdg_config_home

if TYPE_CHECKING:
    from pathlib import Path

USER_AGENT = "YCast"

# initialize it start
VAR_PATH: Path | None = None
CACHE_PATH: Path | None = None
stations_file_by_config: Path | None = None
LOG = logging.getLogger(__name__)


class Directory:
    def __init__(
        self: "Directory", name: str, item_count: int, display_name: str | None = None
    ) -> None:
        self.name = name
        self.item_count = item_count
        if display_name:
            self.display_name = display_name
        else:
            self.display_name = name

    def to_dict(self: "Directory") -> dict[str, str | int]:
        return {"name": self.name, "display_name": self.display_name, "count": self.item_count}


def mk_writeable_dir(path: Path) -> Path | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        LOG.exception("Could not create base folder (%s) because of access permissions", path)
        return None
    return path


def init_base_dir(path_element: str) -> None:
    global VAR_PATH, CACHE_PATH
    if VAR_PATH is None:
        VAR_PATH = xdg_config_home() / path_element
    if CACHE_PATH is None:
        CACHE_PATH = xdg_cache_home() / path_element
    LOG.info("Initialise base directories for %s", path_element)
    LOG.debug("   Config: %s", VAR_PATH)
    LOG.debug("   Cache:  %s", CACHE_PATH)
    mk_writeable_dir(VAR_PATH)
    mk_writeable_dir(CACHE_PATH)


def generate_station_id_with_prefix(uid: str, prefix: str) -> str | None:
    if not prefix or len(prefix) != 2:
        LOG.error("Invalid station prefix length (must be 2)")
        return None
    if not uid:
        LOG.error("Missing station id for full station id generation")
        return None
    return f"{prefix}_{uid}"


def get_station_id_prefix(uid: str) -> str | None:
    if len(uid) < 4:
        LOG.error("Could not extract stationid (Invalid station id length)")
        return None
    return uid[:2]


def get_station_id_without_prefix(uid: str) -> str | None:
    if len(uid) < 4:
        LOG.error("Could not extract stationid (Invalid station id length)")
        return None
    return uid[3:]


def get_cache_path(cache_name: str | None) -> Path:
    cache_path = CACHE_PATH
    assert cache_path is not None
    if cache_name is not None:
        cache_path = cache_path / cache_name
    try:
        cache_path.mkdir(exist_ok=True)
    except PermissionError:
        LOG.exception(
            "Could not create cache folders (%s) because of access permissions", cache_path
        )
        raise
    return cache_path


def get_var_path() -> Path:
    assert VAR_PATH is not None
    try:
        VAR_PATH.mkdir(exist_ok=True)
    except PermissionError:
        LOG.exception(
            "Could not create cache folders (%s) because of access permissions", VAR_PATH
        )
        raise
    return VAR_PATH


def get_recently_file(missing_ok: bool = False) -> Path:
    recently = get_var_path() / "recently.yml"
    if not recently.exists() and not missing_ok:
        raise FileNotFoundError
    return recently


def get_filter_file() -> Path:
    return get_var_path() / "filter.yml"


def get_stations_file() -> Path:
    if stations_file_by_config is not None:
        stations = stations_file_by_config
    else:
        stations = get_var_path() / "stations.yml"
    if not stations.exists():
        raise FileNotFoundError
    return stations


def set_stations_file(stations_file: Path) -> None:
    global stations_file_by_config
    if stations_file:
        stations_file_by_config = stations_file


def get_checksum(feed: str, charlimit: int = 12) -> str:
    hash_feed = feed.encode()
    hash_object = hashlib.md5(hash_feed)  # noqa: S324
    digest = hash_object.digest()
    xor_fold = bytearray(digest[:8])
    for i, b in enumerate(digest[8:]):
        xor_fold[i] ^= b
    digest_xor_fold = "".join(format(x, "02x") for x in bytes(xor_fold))
    return str(digest_xor_fold[:charlimit]).upper()


def read_yaml_file(path: Path) -> dict | None:
    try:
        with path.open() as f:
            y = yaml.safe_load(f)
            assert isinstance(y, dict)
            return y
    except FileNotFoundError:
        LOG.warning("YAML file '%s' not found", path)
    except (yaml.YAMLError, AssertionError):
        LOG.exception("YAML format error in '%s'", path)
    return None


def write_yaml_file(path: Path, dictionary: dict) -> bool:
    try:
        with path.open("w") as f:
            # no sort please
            yaml.dump(dictionary, f, sort_keys=False)
            return True
    except yaml.YAMLError:
        LOG.exception("YAML format error in '%':\n    %s", path)
    except Exception:
        LOG.exception("File not written '%s':\n    %s", path)
    return False


def read_lines_from_file(path: Path) -> list[str]:
    try:
        with path.open() as f:
            return f.readlines()
    except FileNotFoundError:
        LOG.warning("TXT file '%s' not found", path)
    return []


def write_lines_to_file(path: Path, line_list: list[str]) -> bool:
    try:
        with path.open() as f:
            f.writelines(line_list)
            return True
    except Exception:
        LOG.exception("File not written '%s':\n    %s", path)
    return False
