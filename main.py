#!/usr/bin/env python

__author__ = "M Nasimul Haque (nasim.haque@gmail.com)"
__version__ = "0.1"
__copyright__ = "Copyright (c) 2010 M Nasimul Haque"
__license__ = "New-style BSD"

import csv
import datetime
import logging
import re
import StringIO

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from google.appengine.api import urlfetch, memcache
from BeautifulSoup import BeautifulSoup


dseroot = "http://www.dsebd.org/"
dselatest = dseroot + "latest_share_price_all.php"
dsesanere = re.compile(r'<body[^>]*>')
datere = re.compile(r'[a-zA-Z]{3}\s*\d{2},\s*\d{4}\s*at\s*\d{2}:\d{2}:\d{2}')

cselatest = "http://www.csebd.com/trade/top.htm"
csedatere = re.compile(r'Date: '
                       r'[a-zA-Z]{3}\s*\d{2}\s*\d{4}\s*\d{1,2}:\d{1,2}(AM|PM)')
csedatare = re.compile(r'\w+\s*')

fetch_error_message = 'Sorry, there was an error fetching data from main server.'

time_key = 'timekey'
data_key = 'csvdata'
cse_key = 'csedata'
csedate_key = 'csedate'
cache_time = 10 * 60 # ten minutes

class DSEHandler(webapp.RequestHandler):

    def _get_time(self):
        last_update = memcache.get(time_key)
        if last_update:
            return last_update

        response = urlfetch.fetch(dseroot)
        if response.status_code == 200:
            last_update = datere.search(response.content).group()
            last_update = last_update.replace(' ', '')
            last_update = datetime.datetime.strptime(last_update, "%b%d,%Yat"
                                                     "%H:%M:%S")
            logging.info("Last update on %s" % (last_update))
            memcache.set(time_key, last_update, cache_time)
            return last_update

    def get(self):
        last_update = self._get_time()
        csvname = 'dse-%s.csv' % last_update.isoformat()

        self.response.headers.add_header('content-disposition',
                                         'attachment', filename=csvname)
        self.response.headers['Content-Type'] = 'text/csv'

        csvdata = memcache.get(data_key)
        if csvdata:
            self.response.out.write(csvdata)
            logging.info('returning from cache')
            return

        dseresult = urlfetch.fetch(dselatest)
        if not dseresult.status_code == 200:
            self.response.out.write(fetch_error_message)
            return

        dsecontent = dseresult.content
        dsecontent = dsesanere.sub('<body>', dsecontent)

        soup = BeautifulSoup(dsecontent)
        headtr = soup.body.table.tr.findAll('b')

        output = StringIO.StringIO()
        csvfile = csv.writer(output)
        heads = []
        for h in headtr:
            heads.append(str(h.contents[0]).replace('&nbsp;', '').strip())

        heads.insert(1, "Date Time")
        csvfile.writerow(heads)

        data = soup.body.table.findAll('tr')[1:]
        for row in data:
            row = row.findAll('td')[1:]
            d = [row[0].a.contents[0],]
            d.append(last_update)
            for col in row[1:]:
                d.append(col.find(text=True))

            if d[-1] != '0':
                csvfile.writerow(d)

        csvdata = output.getvalue()
        output.close()

        self.response.out.write(csvdata)

        memcache.set(data_key, csvdata, cache_time)

        logging.info('fetched real data')


class CSEHandler(webapp.RequestHandler):

    def get(self):
        last_update = memcache.get(csedate_key)
        if last_update:
            csvname = 'cse-%s.csv' % last_update.isoformat()

        cseresult = urlfetch.fetch(cselatest)
        if not cseresult.status_code == 200:
            self.response.out.write(fetch_error_message)
            return

        content = cseresult.content
        if not last_update:
            csvname = csedatere.search(content).group()
            logging.info(csvname)

        print content
        print csedatare.search(content).group()

        self.response.headers.add_header('content-disposition',
                                         'attachment', filename=csvname)
        self.response.headers['Content-Type'] = 'text/csv'
        csvdata = memcache.get(cse_key)
        if csvdata:
            return


def main():
  application = webapp.WSGIApplication([('/', DSEHandler),
                                        ('/cse', CSEHandler)],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
