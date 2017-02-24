from __future__ import print_function

from datetime import datetime
import scrapy
import requests
import json
import time

from ..models import station as def_station

streema_collection = 'streema'
Station = def_station(streema_collection)


def fetch_nowplaying_info(url):
    retries = 3
    while retries > 0:
        retries -= 1
        try:
            itunes_info = requests.get(url).json()
            if itunes_info.get('status') in ['ok', 'unavailable']:
                return itunes_info
        except:
            pass
        time.sleep(3)
    return {}


class StreemaSpider(scrapy.Spider):
    name = streema_collection
    root = 'http://streema.com'

    ids = set()

    # start_urls = [
    #     '%s/radios' % root,
    # ]
    start_urls = [
        '%s/radios/region/Asia' % root,
        '%s/radios/region/North_America' % root,
        '%s/radios/region/Europe' % root,
        '%s/radios/region/Oceania' % root,
        '%s/radios/region/South_America' % root,
        '%s/radios/region/Central_America' % root,
        '%s/radios/region/Africa' % root,
    ]

    def parse(self, response):
        # return self.parse_index(response)
        return self.parse_region(response)

    def parse_index(self, response):
        regions = response.css('div.geo-list > ul')[0]
        for region in regions.css('li'):
            # name = region.css('a::text').extract_first().strip()
            yield scrapy.Request(
                response.urljoin(region.css('a ::attr(href)').extract_first()),
                callback=self.parse_region
            )

    def parse_region(self, response):
        regions = response.css('div.geo-list > div.row > ul > li')
        for region in regions:
            yield scrapy.Request(
                response.urljoin(region.css('a ::attr(href)').extract_first().strip()),
                callback=self.parse_region
            )
        # if len(regions) == 0:
        for station in self.parse_station(response):
            yield station

    def parse_station(self, response):
        print('---- scrawl radio stations on %s' % response.url)
        stations = response.css('div.results div.items-list > div.item')
        for station in stations:
            def extrace_field(field):
                sel = station.css(field)
                return sel.extract_first().strip() if len(sel) > 0 else ""

            try:
                media_id = extrace_field('div.item-name div::attr(data-radio-id)')
                data_url = response.urljoin(extrace_field('::attr(data-url)') or '/radios/play/%s' % media_id)
                data_profile_url = response.urljoin(extrace_field('::attr(data-profile-url)') or extrace_field('div.item-name h5 a::attr(href)'))
                cover_url = extrace_field('div.item-logo img::attr(src)')
                title = extrace_field('div.item-name h5 a::text') or extrace_field('div.item-name h5::text')
                band = extrace_field('div.item-name p.band-dial::text')
                genres = map(lambda genre: genre.extract().strip(), station.css('div.item-extra div.item-info > p.genre > span::text'))
                locations = map(lambda loc: loc.extract().strip(), station.css('div.item-extra div.item-info > p.location > span::text'))
                rating = extrace_field('div.item-extra div.item-rating > p::text')

                if media_id not in StreemaSpider.ids and Station.objects(media_id=media_id, streams__exists=True).count() == 0 and \
                        Station.objects(media_id=media_id, extra__play_info__exists=True).count() == 0:
                    StreemaSpider.ids.update([media_id])
                    info_url = "http://nowrelinch.streema.com/nowplaying/%s" % media_id
                    station_dict = {
                        'cover': cover_url,
                        'title': title,
                        'genres': genres,
                        'band': band,
                        'extra__locations': locations,
                        'extra__rating': rating,
                        'updated_at': datetime.now(),
                        'referers__player_url': data_url,
                        'referers__profile_url': data_profile_url,
                        'referers__info_url': info_url,
                        'referers__referer': response.url,
                    }

                    # itunes_info = fetch_nowplaying_info(info_url)
                    # if itunes_info:
                    #     station_dict['extra__itunes_info'] = itunes_info
                    #     stream = itunes_info.get('source', {}).get('stream', None)
                    #     if stream:
                    #         station_dict['streams'] = [stream]

                    if len(locations) > 0:
                        station_dict['country'] = locations[-1]
                    if len(locations) > 1:
                        station_dict['city'] = locations[-2].split(',')[0]

                    Station.objects(media_id=media_id).update_one(
                        upsert=True,
                        **station_dict
                    )
                    yield scrapy.Request(
                        response.urljoin(data_profile_url),
                        callback=self.parse_station_profile
                    )

                    yield scrapy.Request(
                        response.urljoin(data_url),
                        callback=self.parse_station_play
                    )

                    st = Station.objects(media_id=media_id).get()
                    yield {
                        'media_id': st.media_id,
                        'title': st.title,
                        'country': st.description,
                        'city': st.city,
                        'genres': st.genres,
                    }
            except Exception, e:
                print(e)

        # go to next page for more stations
        next_page = response.css('ul.pager > li.next > a::attr(href)')
        if len(next_page) > 0:
            yield scrapy.Request(
                response.urljoin(next_page.extract_first()),
                self.parse_station
            )

    def parse_station_profile(self, response):
        try:
            links = {}
            website = response.css('div#radio-contact a.radio-website-link::attr(href)').extract_first()
            if website:
                links['website'] = website.strip()
            for link in response.css('div#radio-contact a.radio-resource-link'):
                links[link.css('::text').extract_first().strip()] = link.css('::attr(href)').extract_first().strip()

            media_id = response.css('p::attr(data-radio)').extract_first()

            station = Station.objects(media_id=media_id).get()
            station.contact = links

            description = response.css('div#radio-info div.radio-description span[data-truncated]::text').extract_first()
            if description:
                description = description.strip()
                desc_rest = response.css('div#radio-info div.radio-description span[data-rest]::text').extract_first()
                if desc_rest:
                    description = "%s%s" % (description, desc_rest.strip())
                station.description = description

            city = response.css('span.radio-city::text').extract_first()
            if city:
                city = city.strip()
                station.city = city
            country = response.css('span[itemprop="addressCountry"]::text').extract_first()
            if country:
                country = country.strip()
                station.country = country
            language = response.css('span.radio-language::text').extract_first()
            if language:
                language = language.strip()
                station.language = language

            station.save()
        except Exception, e:
            print(e)

    def parse_station_play(self, response):
        try:
            media_id = response.css('p[data-radio]::attr(data-radio)').extract_first()
            play_info = json.loads(response.css('script[type="text/javascript"]').re_first(r'ST\.radio\s*=\s*(.*?);\s*ST\.radio'))
            station = Station.objects(media_id=media_id).get()
            station.extra['play_info'] = play_info
            if not station.title and play_info.get('name'):
                station.title = play_info.get('name')
            if not station.country and play_info.get('country'):
                station.country = play_info.get('country')
            if not station.city and play_info.get('city'):
                station.city = play_info.get('city')
            if not station.language and play_info.get('language'):
                station.language = play_info.get('language')
            if not station.contact.get('website') and play_info.get('website'):
                station.contact['website'] = play_info.get('website')
            if not station.streams:
                station.streams = []
            for stream in play_info.get('streams', []):
                found = filter(lambda s: s.get('url') == stream.get('url'), station.streams)
                if not found and not stream.get('is_external', False):
                    station.streams += [stream]
            cover_full = response.css('script[type="text/javascript"]').re_first(r'ST\.radio\.logo_full\s*=\s*{\s*url\s*:\s*"(.*?)"\s*}\s*;')
            if cover_full:
                station.cover_full = cover_full

            station.save()
        except Exception, e:
            print(e)
