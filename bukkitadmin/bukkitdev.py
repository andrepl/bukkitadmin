from __future__ import absolute_import
from datetime import datetime
import os
from bs4 import NavigableString

import feedparser
import requests
import time

from .util import download_file, get_page_soup

DEBUG = 'BUKKITADMIN_DEBUG' in os.environ

class  PluginSource(object):

    source_type = "bukkitdev"
    name = 'bukkitdev'

    def search_result_url(self, search_result):
        url = self._get_download_url(search_result['slug'])
        return url, {'slug': search_result['slug'], 'last_download_url': url}

    def search(self, searchstr):
        soup = get_page_soup("http://dev.bukkit.org/bukkit-plugins/?search=%s" % (searchstr,))
        tbl = soup.find("table", {'class': "listing"}).find("tbody").findAll('tr', {'class': 'row-joined-to-next'})
        results = []
        for row in tbl:
            link = row.find('h2').contents[0]
            next = row.nextSibling
            while isinstance(next, NavigableString):
                next = next.nextSibling
            results.append(dict(
                name=link.text,
                last_updated=datetime.fromtimestamp(int(row.find('td', 'col-date').find('span', 'standard-date')['data-epoch'])),
                authors=[a.text for a in row.find('td', 'col-user').findAll('a')],
                summary=next.td.get_text(),
                slug=link['href'].strip('/').split('/')[-1],
            ))
        return results

    def get_slug(self, plugin_name):
        time.sleep(0.5)
        soup = get_page_soup("http://dev.bukkit.org/bukkit-plugins/?search=%s" % (plugin_name,))
        if DEBUG:
            print "results soup", soup
        tbl = soup.find("table", {'class': "listing"}).find("tbody").findAll('tr', {'class': 'row-joined-to-next'})
        for row in tbl:
            link = row.find('h2').contents[0]
            if link.text.lower() == plugin_name.lower():
                return str(link['href'].strip('/').split('/')[-1])

    def _get_download_url(self, slug):
        feed_url = "http://dev.bukkit.org/bukkit-plugins/%s/files.rss" % (slug,)
        if DEBUG:
            print "fetching %s" % (feed_url,)
        time.sleep(0.5)
        feed = feedparser.parse(feed_url)
        if DEBUG:
            print "feed Entries: ", len(feed.entries)
        if not feed.entries:
            return None
        url = feed.entries[0]['links'][0]['href']
        time.sleep(0.5)
        if DEBUG:
            print "fetching %s" % (url,)
        soup = get_page_soup(url)
        if DEBUG:
            print "page: ", soup.find("title")
        return soup.find('a', text="Download")['href']

    def get_download_url(self, plugin):
        meta = plugin.get_meta()
        if meta is None or not meta.get('slug', None):
            if meta is None:
                meta = {}
            meta['slug'] = self.get_slug(plugin.name)
            if meta['slug'] is None:
                return None
            else:
                plugin.set_meta(meta)
        return self._get_download_url(meta['slug'])

    def download_plugin(self, plugin):
        return download_file(self.get_download_url(plugin))

