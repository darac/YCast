from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import requests
from PIL import Image

import ycast.generic as generic
from ycast import __version__

if TYPE_CHECKING:
    import my_stations
    import radiobrowser

MAX_SIZE = 290
CACHE_NAME = "icons"
LOG = logging.getLogger(__name__)


def get_icon(station: radiobrowser.Station | my_stations.Station) -> bytes | None:
    cache_path = generic.get_cache_path(CACHE_NAME)
    if not cache_path:
        return None

    # make icon filename from favicon-address
    station_icon_file = cache_path / (generic.get_checksum(station.icon) + ".jpg")
    if not station_icon_file.exists():
        LOG.debug(
            "Station icon cache miss. Fetching and converting station icon for station id '%s'",
            station.id,
        )
        headers = {"User-Agent": f"{generic.USER_AGENT}/{__version__}"}
        try:
            response = requests.get(url=station.icon, headers=headers, timeout=(3.05, 27))
        except requests.exceptions.ConnectionError:
            LOG.exception("Connection to station icon URL failed")
            return None
        if response.status_code != 200:
            LOG.debug(
                "Could not get station icon data from %s (HTML status %s)",
                station.icon,
                response.status_code,
            )
            return None
        try:
            image = Image.open(io.BytesIO(response.content))
            image = image.convert("RGB")
            if image.size[0] > image.size[1]:
                ratio = MAX_SIZE / image.size[0]
            else:
                ratio = MAX_SIZE / image.size[1]
            image = image.resize((int(image.size[0] * ratio), int(image.size[1] * ratio)))
            image.save(station_icon_file, format="JPEG")
        except Exception:
            LOG.exception("Station icon conversion error")
            return None
    try:
        with station_icon_file.open("rb") as f:
            image_conv = f.read()
    except PermissionError:
        LOG.exception(
            "Could not access station icon file in cache (%s) because of access permissions",
            station_icon_file,
        )
        return None
    return image_conv
