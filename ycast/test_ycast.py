import logging
import unittest

from ycast import generic, my_filter, my_recent_station, radiobrowser


class MyTestCase(unittest.TestCase):
    logging.getLogger().setLevel(logging.DEBUG)
    generic.init_base_dir("test_ycast")
    my_filter.init_filter_file()

    def test_verify_values(self: "MyTestCase") -> None:
        assert my_filter.verify_value(None, None)
        assert my_filter.verify_value("", None)
        assert my_filter.verify_value("", "")
        assert my_filter.verify_value(None, "")
        assert my_filter.verify_value(3, 3)
        assert my_filter.verify_value("3", 3)
        assert my_filter.verify_value("3", "3")
        assert my_filter.verify_value("3", "3,4,5")
        assert my_filter.verify_value(["3", "5"], "3")
        assert my_filter.verify_value(["3", "5"], "3,6")
        assert my_filter.verify_value([3, 4, 5, 6], 5)

        assert not my_filter.verify_value("", "3")
        assert not my_filter.verify_value(3, 4)
        assert not my_filter.verify_value("3", 4)
        assert not my_filter.verify_value("4", "3")
        assert not my_filter.verify_value(["3,4,5,6"], "9")
        assert not my_filter.verify_value(["3,4,5,6"], "9,8")

    def test_init_filter(self: "MyTestCase") -> None:
        my_filter.begin_filter()
        filter_dictionary = {"whitelist": my_filter.allow_list, "blacklist": my_filter.block_list}
        for elem in filter_dictionary:
            logging.warning("Name filtertype: %s", elem)
            filter_param = filter_dictionary[elem]
            if filter_param:
                for par in filter_param:
                    logging.warning("    Name parameter: %s", par)
            else:
                logging.warning("    <empty list>")

    def test_station_search(self: "MyTestCase") -> None:
        # hard test for filter
        my_filter.allow_list = {}
        my_filter.block_list = {}
        stations_unfiltered = radiobrowser.search("Pinguin Pop")
        logging.info("Stations found (%d)", len(stations_unfiltered))
        assert len(stations_unfiltered)
        my_filter.allow_list = {}
        my_filter.block_list = {"countrycode": "NL"}
        stations_filtered = radiobrowser.search("Pinguin Pop")
        logging.info("Stations found (%d)", len(stations_filtered))
        assert len(stations_filtered) < len(stations_unfiltered)
        assert all(station in stations_unfiltered for station in stations_filtered)

    def test_station_by_country(self: "MyTestCase") -> None:
        my_filter.allow_list = {"codec": "OGG"}
        my_filter.block_list = {}
        stations = radiobrowser.get_stations_by_country("Germany")
        logging.info("Stations (%d)", len(stations))
        # Currently yields 40 but is not fixed of course
        assert 20 < len(stations) < 70

    def test_station_by_language(self: "MyTestCase") -> None:
        my_filter.allow_list = {"codec": "AAC"}
        my_filter.block_list = {"countrycode": "NL"}
        stations = radiobrowser.get_stations_by_language("dutch")
        logging.info("Stations (%d)", len(stations))
        # With this filter there is only 1 (atm).
        assert len(stations)

    def test_station_by_genre(self: "MyTestCase") -> None:
        my_filter.allow_list = {"bitrate": 320}
        my_filter.block_list = {}
        stations = radiobrowser.get_stations_by_genre("rock")
        logging.info("Stations (%d)", len(stations))
        # Currently yields 86 but is not fixed of course
        assert 50 < len(stations) < 200

    def test_station_by_votes(self: "MyTestCase") -> None:
        my_filter.allow_list = {}
        my_filter.block_list = {}
        stations = radiobrowser.get_stations_by_votes()
        logging.info("Stations (%d)", len(stations))
        assert len(stations) == my_filter.get_limit("DEFAULT_STATION_LIMIT")
        # stations = radiobrowser.get_stations_by_votes(10000)
        # logging.info("Stations (%d)", len(stations))
        # assert len(stations) == 10000

    def test_get_languages(self: "MyTestCase") -> None:
        my_filter.allow_list = {"languagecodes": ["en", "no"]}
        my_filter.block_list = {}
        result = radiobrowser.get_language_directories()
        logging.info("Languages (%d)", len(result))
        assert len(result) == 2

    def test_get_countries(self: "MyTestCase") -> None:
        # Test for Germany only 1, nach der Wiedervereinigung...
        my_filter.allow_list = {"country": "Germany"}
        my_filter.block_list = {}

        result = radiobrowser.get_country_directories()
        logging.info("Countries (%d)", len(result))
        assert len(result) == 1

    def test_get_genre(self: "MyTestCase") -> None:
        my_filter.allow_list = {"tags": ["rock", "pop"]}
        my_filter.block_list = {}
        result = radiobrowser.get_genre_directories()
        logging.info("Genres (%d)", len(result))
        # Not a useful test, changes all the time
        # assert len(result) < 300

    def test_get_limits(self: "MyTestCase") -> None:
        result = my_filter.get_limit("MINIMUM_COUNT_COUNTRY")
        assert result == 5
        result = my_filter.get_limit("SHOW_BROKEN_STATIONS")
        assert result is False

    def test_recently_hit(self: "MyTestCase") -> None:
        my_recent_station.get_recently_file(missing_ok=True).unlink(missing_ok=True)

        sbv = my_recent_station.get_stations_by_vote()
        assert len(sbv) == 0

        recent = my_recent_station.get_recent_stations()
        assert recent is None

        i = 0
        while i < 10:
            my_recent_station.signal_station_selected(
                f"NAME {i}", f"http://dummy/{i}", f"http://icon{i}"
            )
            i = i + 1

        recent = my_recent_station.get_recent_stations()
        assert recent is not None
        assert my_recent_station.directory_name()
        assert recent[my_recent_station.directory_name()]

        my_recent_station.signal_station_selected(
            "Konverenz: Sport", f"http://dummy/{i}", f"http://icon{i}"
        )
        my_recent_station.signal_station_selected(
            "Konverenz: Sport", f"http://dummy/{i}", f"http://icon{i}"
        )
        my_recent_station.signal_station_selected(
            "Konverenz: Sport", f"http://dummy/{i}", f"http://icon{i}"
        )

        i = 6
        while i < 17:
            my_recent_station.signal_station_selected(
                f"NAME {i}", f"http://dummy/{i}", f"http://icon{i}"
            )
            i = i + 1

        recent = my_recent_station.get_recent_stations()
        assert recent is not None
        assert recent[my_recent_station.directory_name()]

        sbv = my_recent_station.get_stations_by_vote()
        assert len(sbv) == 5

        j = 0
        while j < 6:
            i = 6
            while i < 9:
                my_recent_station.signal_station_selected(
                    f"NAME {i}", f"http://dummy/{i}", f"http://icon{i}"
                )
                i = i + 1
            j = j + 1
        sbv = my_recent_station.get_stations_by_vote()
        assert len(sbv) == 5


if __name__ == "__main__":
    unittest.main()
