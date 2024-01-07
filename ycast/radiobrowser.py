from __future__ import annotations

import base64
import logging
import uuid
from typing import Any

import requests

import ycast.generic as generic
import ycast.vtuner as vtuner
from ycast import __version__, my_filter
from ycast.my_filter import begin_filter, check_station, end_filter, get_limit

API_ENDPOINT = "http://all.api.radio-browser.info"
ID_PREFIX = "RB"
LOG = logging.getLogger(__name__)

station_cache: dict[str, Station] = {}


class Station:
    def __init__(self: "Station", station: dict) -> None:
        self.station_uuid = station.get("stationuuid", None)
        self.id = generic.generate_station_id_with_prefix(
            base64.urlsafe_b64encode(uuid.UUID(self.station_uuid).bytes).decode(), ID_PREFIX
        )
        self.name = station.get("name", None)
        self.url = station.get("url_resolved", station.get("url", None))
        self.icon = station.get("favicon", None)
        self.description = station.get("tags", None)
        self.tags = station.get("tags", "").split(",")
        self.country_code = station.get("countrycode", None)
        self.language = station.get("language", None)
        self.language_codes = station.get("languagecodes", None)
        self.votes = station.get("votes", None)
        self.codec = station.get("codec", None)
        self.bitrate = station.get("bitrate", None)

    def to_vtuner(self: "Station") -> vtuner.Station:
        return vtuner.Station(
            self.id,
            self.name,
            self.description,
            self.url,
            self.icon,
            self.tags[0],
            self.country_code,
            self.codec,
            self.bitrate,
            None,
        )

    def to_dict(self: "Station") -> dict[str, str]:
        return {
            "name": self.name,
            "url": self.url,
            "icon": self.icon,
            "description": self.description,
        }

    def get_playable_url(self: "Station") -> None:
        try:
            playable_url_json = request("url/" + str(self.station_uuid))
            self.url = playable_url_json["url"]

        except (IndexError, KeyError):
            LOG.exception(
                "Could not retrieve first playlist item for station with id '%s'",
                self.station_uuid,
            )


def request(url: str) -> Any:  # noqa: ANN401
    LOG.debug("Radiobrowser API request: %s", url)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"{generic.USER_AGENT}/{__version__}",
    }
    try:
        response = requests.get(f"{API_ENDPOINT}/json/{url}", headers=headers, timeout=(3.05, 27))
    except requests.exceptions.ConnectionError:
        LOG.exception("Connection to Radiobrowser API failed")
        return {}
    if response.status_code != 200:
        LOG.error(
            "Could not fetch data from Radiobrowser API (HTML status %s)", response.status_code
        )
        return {}
    return response.json()


def get_station_by_id(vtuner_id: str) -> Station | None:
    global station_cache
    # decode
    uid_base64 = generic.get_station_id_without_prefix(vtuner_id)
    if uid_base64 is None:
        return None
    uid = str(uuid.UUID(base64.urlsafe_b64decode(uid_base64).hex()))
    if station_cache:
        station = station_cache[vtuner_id]
        if station:
            return station
    # no item in cache, do request
    station_json = request(f"stations/byuuid?uuids={uid}")
    if station_json and len(station_json):
        station = Station(station_json[0])
        if station and station.id is not None:
            station_cache[station.id] = station
        return station
    return None


def get_country_directories() -> list[generic.Directory]:
    api_call = "countries"
    if not get_limit("SHOW_BROKEN_STATIONS"):
        api_call += "?hidebroken=true"
    countries_raw = request(api_call)
    return [
        generic.Directory(name=country.get("name", ""), item_count=country.get("stationcount", 0))
        for country in countries_raw
        if country.get("name", None)
        and country.get("stationcount", None)
        and country.get("stationcount", 0) > int(get_limit("MINIMUM_COUNT_COUNTRY"))
        and my_filter.check_parameter("country", country.get("name"))
    ]


def get_language_directories() -> list[generic.Directory]:
    api_call = "languages"
    if not get_limit("SHOW_BROKEN_STATIONS"):
        api_call += "?hidebroken=true"
    languages_raw = request(api_call)

    return [
        generic.Directory(
            name=language.get("name", ""),
            item_count=language.get("stationcount", 0),
            display_name=language.get("name", "").title(),
        )
        for language in languages_raw
        if language.get("name", None)
        and language.get("stationcount", None)
        and int(language.get("stationcount", 0) > get_limit("MINIMUM_COUNT_LANGUAGE"))
        and my_filter.check_parameter("languagecodes", language.get("iso_639", None))
    ]


def get_genre_directories() -> list[generic.Directory]:
    api_call = "tags"
    if not get_limit("SHOW_BROKEN_STATIONS"):
        api_call += "?hidebroken=true"
    genres_raw = request(api_call)

    return [
        generic.Directory(
            name=genre.get("name", ""),
            item_count=genre.get("stationcount", 0),
            display_name=genre.get("name", "").capitalize(),
        )
        for genre in genres_raw
        if genre.get("name", None)
        and genre.get("stationcount", None)
        and int(genre.get("stationcount", 0)) > get_limit("MINIMUM_COUNT_GENRE")
        and my_filter.check_parameter("tags", genre.get("name", None))
    ]


def get_stations_by_country(country: str) -> list[Station]:
    begin_filter()
    station_cache.clear()
    stations = []
    stations_list_json = request(
        f"stations/search?order=name&reverse=false&countryExact=true&country={country}"
    )
    for station_json in stations_list_json:
        if check_station(station_json):
            cur_station = Station(station_json)
            if cur_station.id is not None:
                station_cache[cur_station.id] = cur_station
            stations.append(cur_station)
    end_filter()
    return stations


def get_stations_by_language(language: str) -> list[Station]:
    begin_filter()
    station_cache.clear()
    stations = []
    stations_list_json = request(
        f"stations/search?order=name&reverse=false&languageExact=true&language={language}"
    )
    for station_json in stations_list_json:
        if check_station(station_json):
            cur_station = Station(station_json)
            if cur_station.id is not None:
                station_cache[cur_station.id] = cur_station
            stations.append(cur_station)
    end_filter()
    return stations


def get_stations_by_genre(genre: str) -> list[Station]:
    begin_filter()
    station_cache.clear()
    stations = []
    stations_list_json = request(
        f"stations/search?order=name&reverse=false&tagExact=true&tag={genre}"
    )
    for station_json in stations_list_json:
        if check_station(station_json):
            cur_station = Station(station_json)
            if cur_station.id is not None:
                station_cache[cur_station.id] = cur_station
            stations.append(cur_station)
    end_filter()
    return stations


def get_stations_by_votes(limit: int = get_limit("DEFAULT_STATION_LIMIT")) -> list[Station]:
    begin_filter()
    station_cache.clear()
    stations = []
    stations_list_json = request(f"stations?order=votes&reverse=true&limit={limit}")
    for station_json in stations_list_json:
        if check_station(station_json):
            cur_station = Station(station_json)
            if cur_station.id is not None:
                station_cache[cur_station.id] = cur_station
            stations.append(cur_station)
    end_filter()
    return stations


def search(name: str, limit: int = get_limit("DEFAULT_STATION_LIMIT")) -> list[Station]:
    begin_filter()
    station_cache.clear()
    stations = []
    stations_list_json = request(
        f"stations/search?order=name&reverse=false&limit={limit}&name={name}"
    )
    for station_json in stations_list_json:
        if check_station(station_json):
            cur_station = Station(station_json)
            if cur_station.id is not None:
                station_cache[cur_station.id] = cur_station
            stations.append(cur_station)
    end_filter()
    return stations
