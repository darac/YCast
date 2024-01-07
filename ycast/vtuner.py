from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from typing import Any

XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'


def get_init_token() -> str:
    return "<EncryptedToken>0000000000000000</EncryptedToken>"


def strip_https(url: str) -> str:
    if url.startswith("https://"):
        url = "http://" + url[8:]
    return url


def add_bogus_parameter(url: str) -> str:
    """
    We need this bogus parameter because some (if not all) AVRs blindly append additional request
    parameters with an ampersand.
      E.g.: '&mac=<REDACTED>&dlang=eng&fver=1.2&startitems=1&enditems=100'.
    The original vTuner API hacks around that by adding a specific parameter or a bogus parameter
    like '?empty=' to the target URL.
    """
    return url + "?vtuner=true"


class Page:
    def __init__(self: "Page") -> None:
        self.items: list = []
        self.count = -1
        self.dont_cache = False

    def add_item(self: "Page", item: Any) -> None:  # noqa: ANN401
        self.items.append(item)

    def set_count(self: "Page", count: int) -> None:
        self.count = count

    def to_xml(self: "Page") -> ElementTree.Element:
        xml = ElementTree.Element("ListOfItems")
        ElementTree.SubElement(xml, "ItemCount").text = str(self.count)
        if self.dont_cache:
            ElementTree.SubElement(xml, "NoDataCache").text = "Yes"
        for item in self.items:
            xml.append(item.to_xml())
        return xml

    def to_string(self: "Page") -> str:
        return XML_HEADER + ElementTree.tostring(self.to_xml()).decode("utf-8")


class Previous:
    def __init__(self: "Previous", url: str) -> None:
        self.url = url

    def to_xml(self: "Previous") -> ElementTree.Element:
        item = ElementTree.Element("Item")
        ElementTree.SubElement(item, "ItemType").text = "Previous"
        ElementTree.SubElement(item, "UrlPrevious").text = add_bogus_parameter(self.url)
        ElementTree.SubElement(item, "UrlPreviousBackUp").text = add_bogus_parameter(self.url)
        return item


class Display:
    def __init__(self: "Display", text: str) -> None:
        self.text = text

    def to_xml(self: "Display") -> ElementTree.Element:
        item = ElementTree.Element("Item")
        ElementTree.SubElement(item, "ItemType").text = "Display"
        ElementTree.SubElement(item, "Display").text = self.text
        return item


class Spacer:
    def to_xml(self: "Spacer") -> ElementTree.Element:
        item = ElementTree.Element("Item")
        ElementTree.SubElement(item, "ItemType").text = "Spacer"
        return item


class Search:
    def __init__(self: "Search", caption: str, url: str) -> None:
        self.caption = caption
        self.url = url

    def to_xml(self: "Search") -> ElementTree.Element:
        item = ElementTree.Element("Item")
        ElementTree.SubElement(item, "ItemType").text = "Search"
        ElementTree.SubElement(item, "SearchURL").text = add_bogus_parameter(self.url)
        ElementTree.SubElement(item, "SearchURLBackUp").text = add_bogus_parameter(self.url)
        ElementTree.SubElement(item, "SearchCaption").text = self.caption
        ElementTree.SubElement(item, "SearchTextbox").text = None
        ElementTree.SubElement(item, "SearchButtonGo").text = "Search"
        ElementTree.SubElement(item, "SearchButtonCancel").text = "Cancel"
        return item


class Directory:
    def __init__(self: "Directory", title: str, destination: str, item_count: int = -1) -> None:
        self.title = title
        self.destination = destination
        self.item_count = item_count

    def to_xml(self: "Directory") -> ElementTree.Element:
        item = ElementTree.Element("Item")
        ElementTree.SubElement(item, "ItemType").text = "Dir"
        ElementTree.SubElement(item, "Title").text = self.title
        ElementTree.SubElement(item, "UrlDir").text = add_bogus_parameter(self.destination)
        ElementTree.SubElement(item, "UrlDirBackUp").text = add_bogus_parameter(self.destination)
        ElementTree.SubElement(item, "DirCount").text = str(self.item_count)
        return item

    def set_item_count(self: "Directory", item_count: int) -> None:
        self.item_count = item_count


class Station:
    def __init__(
        self: "Station",
        uid: str | None,
        name: str,
        description: str,
        url: str,
        icon: str,
        genre: str,
        location: str | None,
        mime: str | None,
        bitrate: str | None,
        bookmark: str | None,
    ) -> None:
        self.uid = uid
        self.name = name
        self.description = description
        self.url = strip_https(url)
        self.track_url: str | None = None
        self.icon = icon
        self.genre = genre
        self.location = location
        self.mime = mime
        self.bitrate = bitrate
        self.bookmark = bookmark

    def set_track_url(self: "Station", url: str) -> None:
        self.track_url = url

    def to_xml(self: "Station") -> ElementTree.Element:
        item = ElementTree.Element("Item")
        ElementTree.SubElement(item, "ItemType").text = "Station"
        ElementTree.SubElement(item, "StationId").text = self.uid
        ElementTree.SubElement(item, "StationName").text = self.name
        if self.track_url:
            ElementTree.SubElement(item, "StationUrl").text = self.track_url
        else:
            ElementTree.SubElement(item, "StationUrl").text = self.url
        ElementTree.SubElement(item, "StationDesc").text = self.description
        ElementTree.SubElement(item, "Logo").text = self.icon
        ElementTree.SubElement(item, "StationFormat").text = self.genre
        ElementTree.SubElement(item, "StationLocation").text = self.location
        ElementTree.SubElement(item, "StationBandWidth").text = str(self.bitrate)
        ElementTree.SubElement(item, "StationMime").text = self.mime
        ElementTree.SubElement(item, "Relia").text = "3"
        ElementTree.SubElement(item, "Bookmark").text = self.bookmark
        return item
