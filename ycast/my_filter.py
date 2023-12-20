from __future__ import annotations

import logging
from typing import Sequence, Sized

from ycast import generic

allow_list: dict[str, str | int | list[str]] = {"lastcheckok": 1}
block_list: dict[str, str | int | list[str]] = {}
limit_list: dict[str, int | bool] = {}
limit_defs = {
    "DEFAULT_STATION_LIMIT": 200,
    "MINIMUM_COUNT_COUNTRY": 5,
    "MINIMUM_COUNT_GENRE": 40,
    "MINIMUM_COUNT_LANGUAGE": 5,
    "SHOW_BROKEN_STATIONS": False,
}
parameter_failed_list: dict[str, int] = {}
count_used = 0
count_hit = 0
LOG = logging.getLogger(__name__)


def init_filter_file() -> None:
    global allow_list, block_list, limit_list
    LOG.info("Reading Limits and Filters")
    filter_dictionary = generic.read_yaml_file(generic.get_filter_file()) or {}

    allow_list = (
        allow_list
        | filter_dictionary.get("whitelist", {"lastcheckok": 1})
        | filter_dictionary.get("allowlist", {})
    )

    block_list = (
        block_list
        | filter_dictionary.get("blacklist", {})
        | filter_dictionary.get("blocklist", {})
    )

    set_limits(filter_dictionary.get("limits", {}))


def write_filter_config() -> None:
    global limit_list
    filter_dictionary: dict[str, str | dict] = {
        "whitelist": allow_list,
        "blacklist": block_list,
    }
    if len(limit_list) > 0:
        filter_dictionary["limits"] = limit_list
    generic.write_yaml_file(generic.get_var_path() / "filter.yml", filter_dictionary)


def begin_filter() -> None:
    global parameter_failed_list
    global count_used
    global count_hit
    count_used = 0
    count_hit = 0

    # init_filter_file()

    parameter_failed_list.clear()


def end_filter() -> None:
    if parameter_failed_list:
        LOG.info("(%d/%d) stations filtered by: %s", count_hit, count_used, parameter_failed_list)
    else:
        LOG.info("(%d/%d) stations filtered by: <no filter used>")


def parameter_failed_evt(param_name: str) -> None:
    count = 1
    old = None
    if parameter_failed_list:
        old = parameter_failed_list.get(param_name)
    if old:
        count = old + 1
    parameter_failed_list[param_name] = count


def verify_value(ref_val: list | str | int | None, val: list | str | int | None) -> bool:
    val_list: Sequence[str | int | None] = []
    if isinstance(val, str) and "," in val:
        val_list = val.split(",")
    elif isinstance(val, list):
        val_list = val
    else:
        val_list = [val]

    for v in val_list:
        if v is None:
            v = ""
        if isinstance(ref_val, list):
            return v in ref_val
        if str(ref_val) == str(v):
            return True
        if ref_val is None and isinstance(v, Sized):
            return len(v) == 0
    #        if type(val) is int:
    ##            return val == int(ref_val)
    #    if val:
    #        return ref_val.find(str(val)) >= 0
    return False


def check_parameter(parameter_name: str, val: list | str | int | None) -> bool:
    if (
        block_list
        and parameter_name in block_list
        and verify_value(block_list[parameter_name], val)
    ):
        return False
    if allow_list and parameter_name in allow_list:
        return verify_value(allow_list[parameter_name], val)
    return True


def check_station(station_json: dict) -> bool:
    global count_used
    global count_hit
    count_used = count_used + 1
    station_name = station_json.get("name", None)
    if not station_name:
        # müll response
        LOG.debug(station_json)
        return False
    # oder verknüpft
    if block_list:
        for param_name in block_list:
            val = station_json.get(param_name, None)
            if verify_value(block_list[param_name], val):
                parameter_failed_evt(param_name)
                return False

    # und verknüpft
    if allow_list:
        for param_name in allow_list:
            val = station_json.get(param_name, None)
            if val is not None and not verify_value(allow_list[param_name], val):
                # attribut in json vorhanden
                parameter_failed_evt(param_name)
                return False
    count_hit = count_hit + 1
    return True


def get_limit(param_name: str) -> int | bool:
    return limit_list.get(param_name, limit_defs.get(param_name, 0))


def get_limit_list() -> dict[str, int | bool]:
    return limit_defs | limit_list


def set_limits(limits: dict[str, int | bool]) -> dict[str, int | bool]:
    global limit_list, limit_defs_int, limit_defs_bool
    for limit in limits:
        if limits[limit] is None:
            limit_list.pop(limit, None)
        elif limit in limit_defs:
            if (isinstance(limits[limit], int) and limits[limit] > 0) or isinstance(
                limits[limit], bool
            ):
                limit_list[limit] = limits[limit]
        else:
            LOG.error("Invalid limit %s", limit)
    return get_limit_list()
