from __future__ import absolute_import
import os

import feedparser
import requests
import time

from .util import download_file, get_page_soup

DEBUG = 'BUKKITADMIN_DEBUG' in os.environ

class  PluginSource(object):

    source_type = "bukkitdev"
    name = 'bukkitdev'

    def search(self, name):
        try:
            slug = self.get_slug(name)
            url = self._get_download_url(slug)
            return url, {'slug': slug, 'last_download_url': url}
        except Exception as e:
            raise e
            return None, {}

    def get_slug(self, plugin_name):
        time.sleep(0.5)
        soup = get_page_soup("http://dev.bukkit.org/bukkit-plugins/?search=%s" % (plugin_name,))
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
        url = feed.entries[0]['links'][0]['href']
        time.sleep(0.5)
        if DEBUG:
            print "fetching %s" % (url,)
        soup = get_page_soup(requests.get(url).text)
        if DEBUG:
            print "page: ", soup.find("title")
        return soup.find('a', text="Download").parent['href']

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

