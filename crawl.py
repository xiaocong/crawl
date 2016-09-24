#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import with_statement

import re
import requests
import sys
import urllib
import collections

if sys.version_info[0] > 2:
    quote_plus = urllib.parse.quote_plus
else:
    quote_plus = urllib.quote_plus


ROOT_URL = "https://www.internet-radio.com"
GENRES_PATH = "/stations/"

# GENRE_RE = (r"<a\s+onClick=\"ga\(.*?'genreclick'.*?\);\".+?href=\"(.+?)\">(.+?)</a>")
GENRE_RE = (r"<dl>.*?"
    "<a\s+href=\"(/stations/.*?/)\">(.*?)</a>"
    ".*?<dd>(.*?)</dd>.*?</dl>")

STATION_RE = (r"<tr>.*?"
    "<a.*?onClick=\"ga\(.*?'play(?:m3u|pls)',\s*'(.*?)'\);\".*?>\.(m3u|pls)</a>"
    ".*?"
    "<a.*?onClick=\"ga\(.*?'play(?:m3u|pls)',\s*'(.*?)'\);\".*?>\.(m3u|pls)</a>"
    ".*?<td>.*?<h4.*?>(.*?)</h4>"
    ".*?<b>(.*?)</b>"
    ".*?</tr>")
TAG_RE = r"<.*?>"


def body(url):
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.text, r.url
        else:
            return "", url
    except:
        return "", url


def get_genres(url):
    '''return dictionary with key=genre name, value= genre url'''
    html, url = body(url)
    result = re.findall(GENRE_RE, html, flags=re.DOTALL)
    return dict(map(lambda x: (x[1], {"path": x[0], "desc": x[2]}), result))


def gen_station(pls_url, pls, m3u_url, m3u, title, subtitle):
    title = re.sub(TAG_RE, "", title)
    subtitle = re.sub(TAG_RE, "", subtitle)
    return {
        "_id": m3u_url,
        "urls": {
            "m3u": m3u_url,
            "pls": pls_url,
        },
        "title": title,
        "subtitle": subtitle,
    }


def genre_pages(root):
    index = 0
    while True:
        index += 1
        origin = "%spage%d" % (root, index)
        html, url = body(origin)
        if len(html) > 0 and url.startswith(origin):
            yield html
        else:
            break


def get_stations(genre, path):
    pathes = path.split("/")
    path = "/".join([quote_plus(p) for p in pathes])
    url = ROOT_URL + path
    print("Retrieving genre %s" % url)
    for page in genre_pages(url):
        stations = re.findall(STATION_RE, page, flags=re.DOTALL)
        for s in stations:
            yield gen_station(*s)
        if len(stations) == 0:
            break


if __name__ == "__main__":
    genres = get_genres(ROOT_URL + GENRES_PATH)

    def genre_factory():
        return {
            "total": 0,
            "stations": []
        }

    total = 0
    stations = collections.defaultdict(genre_factory)
    for genre, grenre_info in genres.items():
        path = grenre_info["path"]
        genre_stations = stations[genre]
        for station in get_stations(genre, path):
            genre_stations['total'] += 1
            genre_stations['stations'].append(station)
            print("\t" + station.get("title"))
        print("Genre %s: %d stations" % (genre, genre_stations['total']))
        total += genre_stations['total']
    print("Total %d stations" % total)
