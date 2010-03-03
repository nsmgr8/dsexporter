#!/usr/bin/env python

__author__ = "M Nasimul Haque (nasim.haque@gmail.com)"
__version__ = "0.1"
__copyright__ = "Copyright (c) 2010 M Nasimul Haque"
__license__ = "New-style BSD"

import csv
import datetime
import os
import logging
import re
import StringIO

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util, template

from google.appengine.api import urlfetch, memcache
from BeautifulSoup import BeautifulSoup


dseroot = "http://www.dsebd.org/"
dselatest = dseroot + "latest_share_price_all.php"

cselatest = "http://www.csebd.com/trade/top.htm"

fetch_error_message = 'Sorry, there was an error fetching data from main server.'

dse_key = 'dsedata'
dsedate_key = 'dsedate'
dse_last_saved_key = 'dselastsaved'
cse_key = 'csedata'
csedate_key = 'csedate'
cache_time = 1 * 60

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

def render(template_name, template_values):
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    return template.render(template_path, template_values)


def _set_csv_header(headers, csvname):
    headers.add_header('content-disposition', 'attachment', filename=csvname)
    headers['Content-Type'] = 'text/csv'


class DSEHandler(webapp.RequestHandler):

    dsesanere = re.compile(r'<body[^>]*>')
    datere = re.compile(r'[a-zA-Z]{3}\s*\d{1,2},\s*\d{4}\s*at\s*\d{2}:\d{2}:\d{2}')

    def _get_time(self):
        last_update = memcache.get(dsedate_key)
        if last_update is not None:
            return last_update

        response = urlfetch.fetch(dseroot)
        if response.status_code == 200:
            last_update = self.datere.search(response.content).group()
            last_update = last_update.replace(' ', '')
            last_update = datetime.datetime.strptime(last_update, "%b%d,%Yat"
                                                     "%H:%M:%S")
            logging.info("Last update on %s" % (last_update))
            memcache.set(dsedate_key, last_update, cache_time)
            return last_update

    def get(self):
        last_update = self._get_time()
        csvname = 'dse-%s.csv' % last_update.isoformat()
        _set_csv_header(self.response.headers, csvname)

        last_saved = memcache.get(dse_last_saved_key)
        if last_saved == last_update:
            csvdata = memcache.get(dse_key)
            if csvdata:
                self.response.out.write(csvdata)
                logging.info('returning from cache')
                return

        dseresult = urlfetch.fetch(dselatest)
        if not dseresult.status_code == 200:
            self.response.out.write(fetch_error_message)
            return

        soup = BeautifulSoup(self.dsesanere.sub('<body>', dseresult.content))
        headtr = soup.body.table.tr.findAll('b')

        output = StringIO.StringIO()
        csvfile = csv.writer(output)
        heads = []
        for h in headtr:
            heads.append(str(h.contents[0]).replace('&nbsp;', '').strip())

        heads.insert(1, "Date")
        heads.insert(2, "Time")
        csvfile.writerow(heads)

        data = soup.body.table.findAll('tr')[1:]
        for row in data:
            row = row.findAll('td')[1:]

            d = [row[0].a.contents[0], last_update.strftime("%m-%d-%Y"),
                 last_update.strftime("%H:%M:%S")]
            for col in row[1:]:
                d.append(col.find(text=True))

            if d[-1] != '0':
                csvfile.writerow(d)

        csvdata = output.getvalue()
        output.close()

        self.response.out.write(csvdata)

        memcache.set(dse_key, csvdata)
        memcache.set(dse_last_saved_key, last_update)
        logging.info('fetched real data')


class CSEHandler(webapp.RequestHandler):

    csedatere = re.compile(r'Date: '
                           r'([a-zA-Z]{3})\s*(\d{1,2})\s*(\d{4})\s*(\d{1,2}):(\d{1,2})(AM|PM)')
    csedatare = re.compile(r'^\s*(\w+).*?'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(-{0,1}\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+', re.MULTILINE)

    def get(self):
        last_update = memcache.get(csedate_key)
        csvdata = memcache.get(cse_key)
        if csvdata and last_update is not None:
            csvname = 'cse-%s.csv' % last_update.isoformat()
            _set_csv_header(self.response.headers, csvname)
            self.response.out.write(csvdata)

            logging.info('retrieved from cache')
            return

        cseresult = urlfetch.fetch(cselatest)
        if not cseresult.status_code == 200:
            self.response.out.write(fetch_error_message)
            return

        soup = BeautifulSoup(cseresult.content)
        precontents = soup.body.findAll('pre')

        sdate = list(self.csedatere.search(precontents[0].contents[0]).groups())
        for i in [1, 3, 4]:
            if len(sdate[i]) == 1:
                sdate[i] = '0' + sdate[i]
        sdate = ' '.join(sdate)
        last_update = datetime.datetime.strptime(sdate,
                                                 '%b %d %Y %I %M %p')
        csvname = 'cse-%s.csv' % last_update.isoformat()

        output = StringIO.StringIO()
        csvfile = csv.writer(output)
        heads = ['Company', 'Date', 'Time', 'Open', 'High', 'Low', 'Close',
                 'Prev. Close', 'Difference', 'Trades', 'Volume',]
        csvfile.writerow(heads)

        contents = precontents[1].contents[0].split('\n')
        for content in contents:
            try:
                data = list(self.csedatare.search(content).groups())
                if data[-1] == '0':
                    continue
                data.insert(1, last_update.strftime("%m-%d-%Y"))
                data.insert(2, last_update.strftime("%H:%M:%S"))
                csvfile.writerow(data)
            except:
                pass

        csvdata = output.getvalue()
        output.close()

        _set_csv_header(self.response.headers, csvname)
        self.response.out.write(csvdata)

        memcache.set(cse_key, csvdata, cache_time)
        memcache.set(csedate_key, last_update, cache_time)
        logging.info('fetched real data')


class MainHandler(webapp.RequestHandler):

    def get(self):
        self.response.out.write(render('index.html', {}))


def main():
  application = webapp.WSGIApplication([('/', MainHandler),
                                        ('/dse', DSEHandler),
                                        ('/cse', CSEHandler)],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
