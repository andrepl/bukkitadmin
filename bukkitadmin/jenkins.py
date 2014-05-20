from __future__ import absolute_import

import re
import urllib
import feedparser

from .util import download_file, get_page_soup, string_diff

class PluginSource(object):

    source_type = "jenkins"

    def __init__(self, name, host):
        self.name = name
        self.host = host

    def search_result_url(self, result):
        try:
            url = self._get_download_url(result['name'])
            return url, {'source': self.name, 'last_download_url': url}
        except:
            return None, {}

    def search(self, searchstr):
        feed = feedparser.parse("http://%s/rssLatest" % (self.host,))
        results = []
        for entry in feed.entries:
            name = entry['title'].split("#")[0].strip()
            if string_diff(name, searchstr) < 0.75:
                results.append({'name': name})
        return results

    def serialize(self):
        return {'type': self.source_type, 'host': self.host}

    def _get_download_url(self, plugin_name):
        url = "http://%s/job/%s/lastSuccessfulBuild/" % (self.host, plugin_name)
        soup = get_page_soup(url)

        h2 = soup.find('h2', text='Module Builds')

        url += urllib.quote(h2.nextSibling.find('a', text=re.compile(r'^' + re.escape(plugin_name) + '.?$', re.IGNORECASE))['href'])
        soup = get_page_soup(url)
        links = filter(lambda e: not (e.text.endswith("-sources.jar") or e.text.endswith("-javadoc.jar")), soup.find('table', {'class': 'fileList'}).findAll('a', text=re.compile(r'.*\.jar')))
        url += urllib.quote(links[0]['href'])
        return url

    def get_download_url(self, plugin):
        return self._get_download_url(plugin.name)

    def download_plugin(self, plugin):
        url = self.get_download_url(plugin)
        return download_file(url)
