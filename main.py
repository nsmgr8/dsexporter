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

dseurl = "http://www.dsebd.org/latest_share_price_all.php"
dsesanere = re.compile('<body[^>]*>')

data_key = 'csvdata'

dt = datetime.timedelta(minutes=10)

class DSEHandler(webapp.RequestHandler):

    def get(self):
        now = datetime.datetime.now()
        csvname = 'dse-%s.csv' % now.isoformat()

        self.response.headers.add_header('content-disposition',
                                         'attachment', filename=csvname)
        self.response.headers['Content-Type'] = 'text/csv'

        csvdata = memcache.get(data_key)
        if csvdata:
            self.response.out.write(csvdata)
            logging.info('returning from cache')
            return

        dseresult = urlfetch.fetch(dseurl)
        if dseresult.status_code == 200:
            dsecontent = dseresult.content
            dsecontent = dsesanere.sub('<body>', dsecontent)

            soup = BeautifulSoup(dsecontent)
            headtr = soup.body.table.tr.findAll('b')

            output = StringIO.StringIO()
            csvfile = csv.writer(output)
            heads = []
            for h in headtr:
                heads.append(
                    str(h).replace('&nbsp;',
                        '').strip('<b>').strip('</b>').strip())

            csvfile.writerow(heads)

            data = soup.body.table.findAll('tr')[1:]
            for row in data:
                row = row.findAll('td')[1:]
                d = [row[0].a.contents[0],]
                for col in row[1:]:
                    d.append(col.find(text=True))

                if d[-1] != '0':
                    csvfile.writerow(d)

            csvdata = output.getvalue()
            output.close()

            self.response.out.write(csvdata)

            memcache.set(data_key, csvdata, 60)

            logging.info('fetched real data')
        else:
            self.response.out.write('Sorry, there was a problem downloading'
                                    ' data from main server!')


def main():
  application = webapp.WSGIApplication([('/', DSEHandler)],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
