from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Mapping, Sequence

import flask
from flask import (
    Flask,
    Request,
    abort,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

import ycast.generic as generic
import ycast.my_filter as my_filter
import ycast.my_stations as my_stations
import ycast.radiobrowser as radiobrowser
import ycast.station_icons as station_icons
import ycast.vtuner as vtuner
from ycast import my_recent_station
from ycast.my_recent_station import signal_station_selected

if TYPE_CHECKING:
    from pathlib import Path

    from flask.typing import ResponseReturnValue
    from werkzeug.wrappers.response import Response

PATH_ROOT = "ycast"
PATH_PLAY = "play"
PATH_STATION = "station"
PATH_SEARCH = "search"
PATH_ICON = "icon"
PATH_MY_STATIONS = "my_stations"
PATH_RADIOBROWSER = "radiobrowser"
PATH_RADIOBROWSER_COUNTRY = "country"
PATH_RADIOBROWSER_LANGUAGE = "language"
PATH_RADIOBROWSER_GENRE = "genre"
PATH_RADIOBROWSER_POPULAR = "popular"

LOG = logging.getLogger(__name__)

station_tracking = False
app = Flask(__name__)


def run(config: Path, address: str = "127.0.0.1", port: int = 8010) -> None:
    try:
        generic.set_stations_file(config)
        app.run(host=address, port=port)
    except PermissionError:
        LOG.exception(
            "No permission to create socket. "
            "Are you trying to use ports below 1024 without elevated rights?"
        )


def get_directories_page(
    subdir: str, directories: list[generic.Directory], request: Request
) -> vtuner.Page:
    page = vtuner.Page()
    if len(directories) == 0:
        page.add_item(vtuner.Display("No entries found"))
        page.set_count(1)
        return page
    for directory in get_paged_elements(directories, request.args):
        vtuner_directory = vtuner.Directory(
            directory.display_name,
            url_for(subdir, _external=True, directory=directory.name),
            directory.item_count,
        )
        page.add_item(vtuner_directory)
    page.set_count(len(directories))
    return page


def get_stations_page(stations: Sequence, request: Request) -> vtuner.Page:
    page = vtuner.Page()
    page.add_item(vtuner.Previous(url_for("landing", _external=True)))
    if len(stations) == 0:
        page.add_item(vtuner.Display("No stations found"))
        page.set_count(1)
        return page
    for station in get_paged_elements(stations, request.args):
        vtuner_station = station.to_vtuner()
        if station_tracking:
            vtuner_station.set_trackurl(
                f"{request.host_url}{PATH_ROOT}/{PATH_PLAY}?id={vtuner_station.uid}"
            )
        vtuner_station.icon = f"{request.host_url}{PATH_ROOT}/{PATH_ICON}?id={vtuner_station.uid}"
        page.add_item(vtuner_station)
    page.set_count(len(stations))
    return page


def get_paged_elements(items: Sequence, request_args: dict) -> Sequence:
    if request_args.get("startitems"):
        offset = int(request_args.get("startitems", 0)) - 1
    elif request_args.get("startItems"):
        offset = int(request_args.get("startItems", 0)) - 1
    elif request_args.get("start"):
        offset = int(request_args.get("start", 0)) - 1
    else:
        offset = 0
    if offset > len(items):
        LOG.warning("Paging offset larger than item count")
        return []

    if request_args.get("enditems"):
        limit = int(request_args.get("enditems", 0))
    elif request_args.get("endItems"):
        limit = int(request_args.get("endItems", 0))
    elif request_args.get("start") and request_args.get("howmany"):
        limit = int(request_args.get("start", 0)) - 1 + int(request_args.get("howmany", 0))
    else:
        limit = len(items)
    if limit < offset:
        LOG.warning("Paging limit smaller than offset")
        return []
    if limit > len(items):
        limit = len(items)

    return items[offset:limit]


def get_station_by_id(
    station_id: str, additional_info: bool = False
) -> radiobrowser.Station | my_stations.Station | None:
    LOG.debug("Looking for station %s", station_id)
    station_id_prefix = generic.get_station_id_prefix(station_id)
    if station_id_prefix == my_stations.ID_PREFIX:
        LOG.debug("  This is one of MY stations")
        return my_stations.get_station_by_id(station_id)
    if station_id_prefix == radiobrowser.ID_PREFIX:
        LOG.debug("  This is a generic station")
        station = radiobrowser.get_station_by_id(station_id)
        if additional_info and station is not None:
            station.get_playable_url()
        return station
    return None


def vtuner_redirect(url: str) -> Response:
    if request and request.host and not re.search(r"^[A-Za-z0-9]+\.vtuner\.com$", request.host):
        LOG.warning(
            "You are not accessing a YCast redirect with a whitelisted host url (*.vtuner.com). "
            "Some AVRs have problems with this. The requested host was: %s",
            request.host,
        )
    return redirect(url, code=302)


@app.route("/setupapp/<path:path>", methods=["GET", "POST"])
def upstream(path: str) -> ResponseReturnValue:
    LOG.debug("upstream **********************")
    if request.args.get("token") == "0":
        return vtuner.get_init_token()
    if request.args.get("search"):
        return station_search()
    if "statxml.asp" in path and request.args.get("id"):
        return get_station_info()
    if "navXML.asp" in path:
        return radiobrowser_landing()
    if "FavXML.asp" in path:
        return my_stations_landing()
    if "loginXML.asp" in path:
        return landing()
    LOG.error("Unhandled upstream query (/setupapp/%s)", path)
    abort(404)
    return None


@app.route("/control/filter/<path:item>", methods=["POST", "GET"])
def set_filters(item: str) -> ResponseReturnValue:
    update_limits = False
    # POST updates the whitelist or blacklist,
    # GET just returns the current attributes/values.
    myfilter: Mapping = {}
    if item.endswith(("blacklist", "blocklist")):
        myfilter = my_filter.block_list
    if item.endswith(("whitelist", "allowlist")):
        myfilter = my_filter.allow_list
    if item.endswith("limits"):
        myfilter = my_filter.get_limit_list()
        update_limits = True
    if request.method == "POST":
        json = request.get_json()
        if update_limits:
            myfilter = my_filter.set_limits(json)
        else:
            for j in json:
                # Attribute with null value removes item from the list otherwise add the attribute
                # or update the value
                if json[j] is None:
                    dict(myfilter).pop(j, None)
                else:
                    dict(myfilter)[j] = json[j]
        my_filter.write_filter_config()
    return flask.jsonify(myfilter)


@app.route("/api/<path:path>", methods=["GET", "POST"])
def landing_api(path: str) -> ResponseReturnValue:
    if request.method == "GET":
        if path.endswith("stations"):
            category = request.args.get("category", "")
            stations: list = []
            if category.endswith("recently"):
                stations = my_recent_station.get_stations_by_recently()
            if category.endswith("voted"):
                stations = radiobrowser.get_stations_by_votes()
            if category.endswith("language"):
                language = request.args.get("language", "german")
                stations = radiobrowser.get_stations_by_language(language)
            if category.endswith("country"):
                country = request.args.get("country", "Germany")
                stations = radiobrowser.get_stations_by_country(country)

            if stations is not None:
                return flask.jsonify([station.to_dict() for station in stations])

        if path.endswith("bookmarks"):
            category = request.args.get("category", "")
            stations = my_stations.get_all_bookmarks_stations()
            if stations is not None:
                return flask.jsonify([station.to_dict() for station in stations])

        if path.endswith("paramlist"):
            category = request.args.get("category", "")
            directories = None
            if category.endswith("language"):
                directories = radiobrowser.get_language_directories()
            if category.endswith("country"):
                directories = radiobrowser.get_country_directories()
            if directories is not None:
                return flask.jsonify([directory.to_dict() for directory in directories])

    if request.method == "POST":
        return flask.jsonify(my_stations.put_bookmark_json(request.get_json()))

    return abort(501, "Not implemented: " + path)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
def landing_root(path: str = "") -> ResponseReturnValue:  # noqa: ARG001
    return render_template("index.html")


@app.route(f"/{PATH_ROOT}/", defaults={"path": ""}, methods=["GET", "POST"])
def landing(_path: str = "") -> ResponseReturnValue:
    LOG.debug("===============================================================")
    page = vtuner.Page()

    page.add_item(
        vtuner.Directory("Radiobrowser", url_for("radiobrowser_landing", _external=True), 4)
    )

    page.add_item(
        vtuner.Directory(
            "My Stations",
            url_for("my_stations_landing", _external=True),
            len(my_stations.get_category_directories()),
        )
    )

    stations = my_recent_station.get_stations_by_vote()
    if stations and len(stations) > 0:
        # make blank line (display is not shown)
        page.add_item(vtuner.Spacer())

        for station in stations:
            vtuner_station = station.to_vtuner()
            if station_tracking:
                vtuner_station.set_track_url(
                    f"{request.host_url}{PATH_ROOT}/{PATH_PLAY}?id={vtuner_station.uid}"
                )
            vtuner_station.icon = (
                f"{request.host_url}{PATH_ROOT}/{PATH_ICON}?id={vtuner_station.uid}"
            )
            page.add_item(vtuner_station)

    else:
        page.add_item(vtuner.Display("'My Stations' feature not configured."))
    page.set_count(-1)
    return page.to_string()


@app.route(f"/{PATH_ROOT}/{PATH_MY_STATIONS}/", methods=["GET", "POST"])
def my_stations_landing() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    directories = my_stations.get_category_directories()
    return get_directories_page("my_stations_category", directories, request).to_string()


@app.route(f"/{PATH_ROOT}/{PATH_MY_STATIONS}/<directory>", methods=["GET", "POST"])
def my_stations_category(directory: str) -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stations = my_stations.get_stations_by_category(directory)
    return get_stations_page(stations, request).to_string()


@app.route(f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/", methods=["GET", "POST"])
def radiobrowser_landing() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    page = vtuner.Page()
    page.add_item(
        vtuner.Directory(
            "Genres",
            url_for("radiobrowser_genres", _external=True),
            len(radiobrowser.get_genre_directories()),
        )
    )
    page.add_item(
        vtuner.Directory(
            "Countries",
            url_for("radiobrowser_countries", _external=True),
            len(radiobrowser.get_country_directories()),
        )
    )
    page.add_item(
        vtuner.Directory(
            "Languages",
            url_for("radiobrowser_languages", _external=True),
            len(radiobrowser.get_language_directories()),
        )
    )
    page.add_item(
        vtuner.Directory(
            "Most Popular",
            url_for("radiobrowser_popular", _external=True),
            len(radiobrowser.get_stations_by_votes()),
        )
    )
    page.set_count(4)
    return page.to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_COUNTRY}/",
    methods=["GET", "POST"],
)
def radiobrowser_countries() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    directories = radiobrowser.get_country_directories()
    return get_directories_page("radiobrowser_country_stations", directories, request).to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_COUNTRY}/<directory>",
    methods=["GET", "POST"],
)
def radiobrowser_country_stations(directory: str) -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stations = radiobrowser.get_stations_by_country(directory)
    return get_stations_page(stations, request).to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_LANGUAGE}/",
    methods=["GET", "POST"],
)
def radiobrowser_languages() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    directories = radiobrowser.get_language_directories()
    return get_directories_page("radiobrowser_language_stations", directories, request).to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_LANGUAGE}/<directory>",
    methods=["GET", "POST"],
)
def radiobrowser_language_stations(directory: str) -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stations = radiobrowser.get_stations_by_language(directory)
    return get_stations_page(stations, request).to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_GENRE}/",
    methods=["GET", "POST"],
)
def radiobrowser_genres() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    directories = radiobrowser.get_genre_directories()
    return get_directories_page("radiobrowser_genre_stations", directories, request).to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_GENRE}/<directory>",
    methods=["GET", "POST"],
)
def radiobrowser_genre_stations(directory: str) -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stations = radiobrowser.get_stations_by_genre(directory)
    return get_stations_page(stations, request).to_string()


@app.route(
    f"/{PATH_ROOT}/{PATH_RADIOBROWSER}/{PATH_RADIOBROWSER_POPULAR}/",
    methods=["GET", "POST"],
)
def radiobrowser_popular() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stations = radiobrowser.get_stations_by_votes()
    return get_stations_page(stations, request).to_string()


@app.route(f"/{PATH_ROOT}/{PATH_SEARCH}/", methods=["GET", "POST"])
def station_search() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    query = request.args.get("search")
    if not query or len(query) < 3:
        page = vtuner.Page()
        page.add_item(vtuner.Display("Search query too short"))
        page.set_count(1)
        return page.to_string()
    # TODO(@THanika): we also need to include 'my station' elements
    # http:///
    stations = radiobrowser.search(query)
    return get_stations_page(stations, request).to_string()


@app.route(f"/{PATH_ROOT}/{PATH_PLAY}", methods=["GET", "POST"])
def get_stream_url() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stationid = request.args.get("id")
    if not stationid:
        LOG.error("Stream URL without station ID requested")
        abort(400)
    station = get_station_by_id(stationid, additional_info=True)
    if station is None:
        LOG.error("Could not get station with id '%s'", stationid)
        abort(404)
    LOG.debug("Station with ID '%s' requested", station.id)  # type: ignore
    return vtuner_redirect(station.url)  # type: ignore


@app.route(f"/{PATH_ROOT}/{PATH_STATION}", methods=["GET", "POST"])
def get_station_info() -> ResponseReturnValue:
    LOG.debug("===============================================================")
    stationid = request.args.get("id")
    if not stationid:
        LOG.error("Station info without station ID requested")
        abort(400)
    station = get_station_by_id(stationid, additional_info=(not station_tracking))
    if not station:
        LOG.error("Could not get station with id '%s'", stationid)
        page = vtuner.Page()
        page.add_item(vtuner.Display("Station not found"))
        page.set_count(1)
        return page.to_string()
    vtuner_station = station.to_vtuner()
    if station_tracking:
        vtuner_station.set_track_url(
            f"{request.host_url}{PATH_ROOT}/{PATH_PLAY}?id={vtuner_station.uid}"
        )
    vtuner_station.icon = f"{request.host_url}{PATH_ROOT}/{PATH_ICON}?id={vtuner_station.uid}"
    page = vtuner.Page()
    page.add_item(vtuner_station)
    page.set_count(1)
    return page.to_string()


@app.route(f"/{PATH_ROOT}/{PATH_ICON}", methods=["GET", "POST"])
def get_station_icon() -> ResponseReturnValue:
    LOG.debug("**********************:  %s", request.url)
    stationid = request.args.get("id")
    if not stationid:
        LOG.error("Station icon without station ID requested")
        abort(400)
    station = get_station_by_id(stationid)
    if not station:
        LOG.error("Could not get station with id '%s'", stationid)
        abort(404)
    signal_station_selected(station.name, station.url, station.icon)  # type: ignore
    if not hasattr(station, "icon") or not station.icon:  # type: ignore
        LOG.warning("No icon information found for station with id '%s'", stationid)
        abort(404)
    station_icon = station_icons.get_icon(station)
    if not station_icon:
        LOG.warning("Could not get station icon for station with id '%s'", stationid)
        abort(404)
    response = make_response(station_icon)
    response.headers.set("Content-Type", "image/jpeg")
    return response
