from __future__ import annotations

import logging

from ycast import generic, my_stations
from ycast.generic import get_recently_file

MAX_ENTRIES = 15
# define a max, so after 5 hits, another station is get better votes
MAX_VOTES = 5
DIRECTORY_NAME = "recently used"
LOG = logging.getLogger(__name__)

recent_stations: dict[str, dict[str, str]] | None = None
voted5_stations: dict[str, str] = {}


class StationVote:
    def __init__(self: "StationVote", name: str, params: str) -> None:
        self.name = name
        param_parts = params.split("|")
        self.url = param_parts[0]
        self.icon = ""
        self.vote = 0
        if len(param_parts) > 1:
            self.icon = param_parts[1]
            if len(param_parts) > 2:
                self.vote = int(param_parts[2])

    def to_params_txt(self: "StationVote") -> str:
        return f"{self.url}|{self.icon}|{self.vote}"

    def to_server_station(self: "StationVote", category: str) -> my_stations.Station:
        return my_stations.Station(self.name, self.url, category, self.icon)


def signal_station_selected(name: str, url: str, icon: str) -> None:
    recently_station_list = get_stations()
    station_hit = StationVote(name, f"{url}|{icon}")
    for recently_station in recently_station_list:
        if name == recently_station.name:
            station_hit.vote = recently_station.vote + 1
            recently_station_list.remove(recently_station)
            break

    recently_station_list.insert(0, station_hit)

    if station_hit.vote > MAX_VOTES:
        for recently_station in recently_station_list:
            if recently_station.vote > 0:
                recently_station.vote = recently_station.vote - 1

    if len(recently_station_list) > MAX_ENTRIES:
        # remove last (oldest) entry
        recently_station_list.pop()

    set_recent_stations(mk_station_dictionary(directory_name(), recently_station_list))


def set_recent_stations(stations: dict) -> None:
    global recent_stations
    recent_stations = stations
    try:
        generic.write_yaml_file(get_recently_file(), recent_stations)
    except FileNotFoundError:
        LOG.debug("No recently file available, silently skipping save")


def mk_station_dictionary(category: str, stations: list[StationVote]) -> dict[str, dict[str, str]]:
    categories = {}
    station_dictionary = {}
    for station in stations:
        station_dictionary[station.name] = station.to_params_txt()

    categories[category] = station_dictionary
    return categories


def get_stations() -> list[StationVote]:
    categories: dict[str, dict[str, str]] = get_recent_stations() or {}
    if not categories:
        return []
    return [
        StationVote(name=station, params=categories.get(category, {}).get(station, ""))
        for category in categories
        for station in categories[category]
    ]


def get_recent_stations() -> dict[str, dict[str, str]] | None:
    # cached recently
    global recent_stations
    if not recent_stations:
        try:
            recent_stations = generic.read_yaml_file(get_recently_file())  # type: ignore
        except FileNotFoundError:
            LOG.debug("No recently file available")
    return recent_stations


def directory_name() -> str:
    stations = get_recent_stations()
    if stations:
        return next(iter(stations.keys()))
    return DIRECTORY_NAME


# used in landing page
def get_stations_by_vote() -> list[my_stations.Station]:
    stations = get_stations()
    stations.sort(key=lambda station: station.vote, reverse=True)
    stations = stations[:5]
    return [station.to_server_station("voted") for station in stations]


def get_stations_by_recently() -> list[my_stations.Station]:
    stations = get_stations()
    return [station.to_server_station(directory_name()) for station in stations]
