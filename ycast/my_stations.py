from __future__ import annotations

import logging
from typing import Iterable

import ycast.generic as generic
import ycast.vtuner as vtuner

ID_PREFIX = "MY"
LOG = logging.getLogger(__name__)


class Station:
    def __init__(self: "Station", name: str, url: str, category: str, icon: str) -> None:
        self.id = generic.generate_station_id_with_prefix(
            generic.get_checksum(name + url), ID_PREFIX
        )
        self.name = name
        self.url = url
        self.tag = category
        self.icon = icon

    def to_vtuner(self: "Station") -> vtuner.Station:
        return vtuner.Station(
            self.id, self.name, self.tag, self.url, self.icon, self.tag, None, None, None, None
        )

    def to_dict(self: "Station") -> dict[str, str]:
        return {"name": self.name, "url": self.url, "icon": self.icon, "description": self.tag}


def get_station_by_id(vtuner_id: str) -> Station | None:
    my_stations_yaml = get_stations_yaml()
    if my_stations_yaml:
        for category in my_stations_yaml:
            for station in get_stations_by_category(category):
                if vtuner_id == station.id:
                    return station
    return None


def get_stations_yaml() -> dict | None:
    from ycast.my_recent_station import get_recent_stations

    my_recently_station = get_recent_stations()
    my_stations = generic.read_yaml_file(generic.get_stations_file())
    if my_stations and my_recently_station:
        my_stations.update(my_recently_station)
    else:
        return my_recently_station
    return my_stations


def get_category_directories() -> list[generic.Directory]:
    my_stations_yaml = get_stations_yaml()
    if not my_stations_yaml:
        return []
    return [
        generic.Directory(name=category, item_count=len(get_stations_by_category(category)))
        for category in my_stations_yaml
    ]


def get_stations_by_category(category: str) -> list[Station]:
    my_stations_yaml = get_stations_yaml()
    if not my_stations_yaml or category not in my_stations_yaml:
        return []

    return [
        Station(
            name=station,
            url=my_stations_yaml[category][station].split("|")[0],
            category=category,
            icon=(
                my_stations_yaml[category][station].split("|")[1]
                if "|" in my_stations_yaml[category][station]
                else ""
            ),
        )
        for station in my_stations_yaml[category]
    ]


def get_all_bookmarks_stations() -> list[Station]:
    bm_stations_category = generic.read_yaml_file(generic.get_stations_file())
    if not bm_stations_category:
        return []

    return [
        Station(
            name=station,
            url=bm_stations_category[category][station].split("|")[0],
            category=category,
            icon=(
                bm_stations_category[category][station].split("|")[1]
                if "|" in bm_stations_category[category][station]
                else ""
            ),
        )
        for category in bm_stations_category
        for station in bm_stations_category[category]
    ]


def put_bookmark_json(elements: Iterable) -> Iterable:
    new_dict: dict[str, dict[str, str]] = {}
    for station in elements:
        LOG.debug("%(description)s ... %(name)s", station)
        if station["description"] not in new_dict:
            new_dict[station["description"]] = {}
        LOG.debug(station)
        if station["icon"] is not None:
            new_dict[station["description"]][station["name"]] = (
                station["url"] + "|" + station["icon"]
            )
        else:
            new_dict[station["description"]][station["name"]] = station["url"]

    generic.write_yaml_file(generic.get_stations_file(), new_dict)
    return elements
