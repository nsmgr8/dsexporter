#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       dsnap.py
#
#  Portions Copyright (c) 2010, M Nasimul Haque
#  Portions Copyright (c) 2010 invarBrass
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of the <organization> nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

__program__ = "PyDSnap"
__logo__ = r'''
             .-.
            ((`-'       <-^-^-^-^-^-^-^-^-^-^-^-^-^-^-^-^->
             \\         <                                 >
              \\        |          PyDSnap 2010           |
       .="""=._))       <                                 >
      ;  '=. "'"        <-v-v-v-v-v-v-v-v-v-v-v-v-v-v-v-v->
       '=="     '''
__description__ = "Captures stock price snapshot of the Dhaka & Chittagong Stock Exchanges\r\n "
__description__ += "Generates CSV output in the standard OHLC format\r\n "
__description__ += "(Compatible with AmiBroker, Meta Stock, Trade Station,\r\n  "
__description__ += "Ninja Trader & other TA tools)"
__author__ = "\tM Nasimul Haque <nasim.haque@gmail.com>\r\n"
__author__ += "\tinvarBrass     <blogtest77@gmail.com>"
__version__ = "0.2"
__copyright__ = "\tPortions copyright (C) 2010 invarBrass\r\n"
__copyright__ += "\tPortions copyright (C) 2010 M Nasimul Haque"

import csv
import datetime
import os
import re
import cStringIO as StringIO
import urllib2
from BeautifulSoup import BeautifulSoup
from optparse import OptionParser

# Constants
DSE_ROOT_URL = "http://www.dsebd.org/"
DSE_LATEST_URL = DSE_ROOT_URL + "latest_share_price_all.php"
CSE_ROOT_URL = "http://www.csebd.com/"
CSE_LATEST_URL = CSE_ROOT_URL + "trade/top.htm"
CSV_OUTPUT_DIR = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'csv')


# Global flags
emit_csv_header = False
process_dse_data = True
verbose_mode = True
csv_filename = ""
filter_inactive_companies = True
dump_data_screen = False

def show_banner():
    if verbose_mode:
        print("\r\n " + __logo__)
        print("\r\n " + __program__ + " " + __version__)
        print(" " + __description__  + "\r\n")
        print(" Author(s):\r\n" + __author__)
        print(" Copyright:\r\n" + __copyright__ + "\r\n")

def log_to_screen(msg):
    if verbose_mode:
        print("[%s] %s" %(datetime.datetime.now().strftime("%H:%M:%S"), msg))

def dump_records(rows):
    if dump_data_screen:
        for row in rows:
            s = ','.join(row)
            print(s)

def parse_options():
    usage = "Usage: %prog [options]"
    parser = OptionParser(usage)
    parser.set_defaults(opt_verbose=True,
                        opt_emit_header=False,
                        opt_dont_prune=False,
                        opt_dump_data=False,
                        opt_process_dse=True)

    parser.add_option("-e", "--header", dest="opt_emit_header",
                      action="store_true",
                      help="append a header line to the CSV file (default: off)")
    parser.add_option("-d", "--dse", dest="opt_process_dse",
                      action="store_true",
                      help="capture DSE snapshot (default: on)")
    parser.add_option("-c", "--cse", dest="opt_process_dse",
                      action="store_false",
                      help="capture CSE snapshot (default: off)")
    parser.add_option("-f", "--file", dest="filename",
                      metavar="FILE",
                      help="save CSV data to FILE")
    parser.add_option("-v", "--verbose",
                      action="store_true",
                      dest="opt_verbose",
                      help="log status information on the screen (default: on)")
    parser.add_option("-q", "--quiet",
                      action="store_false",
                      dest="opt_verbose")
    parser.add_option("-p", "--print",
                      action="store_true",
                      dest="opt_dump_data",
                      help="print captured data on screen (default: off)")
    parser.add_option("-n", "--dont-prune",
                      action="store_true",
                      dest="opt_dont_prune",
                      help="do not filter out non-trading companies (default: off)")
    (options, args)             = parser.parse_args()

    global emit_csv_header, csv_filename, process_dse_data, verbose_mode, filter_inactive_companies, dump_data_screen

    emit_csv_header             = options.opt_emit_header
    csv_filename                = options.filename
    process_dse_data            = options.opt_process_dse
    verbose_mode                = options.opt_verbose
    filter_inactive_companies   = not options.opt_dont_prune
    dump_data_screen            = options.opt_dump_data

class AbstractStockExchangeHandler(object):
    _stock_exchange_name = ""

    def __init__(self, stock_exchange):
        self._stock_exchange_name = stock_exchange

    def download_html(self, url):
        req = urllib2.Request(url)
        req.add_header('Referer', url)
        req.add_header('User-agent', 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.2) Gecko/20100115 Firefox/3.6')
        resp = urllib2.urlopen(req)
        data = resp.read()
        resp.close()
        return data#.replace("\r", '').replace("\n", '')

    def get_filename(self, last_update_time):
        return r'%s%s%s-%s.csv' % (CSV_OUTPUT_DIR, os.sep, self._stock_exchange_name, last_update_time.strftime("%y-%m-%d_%H-%M"))

    def process(): abstract

class DSEHandler(AbstractStockExchangeHandler):

    _RE_HTML_BODY_SANITIZER = re.compile(r'<body[^>]*>')
    _RE_DSE_DATE = re.compile(r'[a-zA-Z]{3}\s*\d{2},\s*\d{4}\s*at\s*\d{2}:\d{2}:\d{2}')

    def __init__(self):
        super(self.__class__,self).__init__("dse")

    def _get_last_update_time(self):
        last_update = datetime.datetime.now()
        response = super(self.__class__,self).download_html(DSE_ROOT_URL)

        if len(response) > 0:
            tmp = self._RE_DSE_DATE.search(response).group()
            tmp = tmp.replace(' ', '')
            last_update = datetime.datetime.strptime(tmp, "%b%d,%Yat%H:%M:%S")

        return last_update

    def process(self):
        log_to_screen("Retrieving the last update time from DSE index page...")
        last_update = self._get_last_update_time()
        log_to_screen("DSE Last updated on " + last_update.isoformat())
        csvname =  (csv_filename != "") and csv_filename or super(self.__class__,self).get_filename(last_update)

        log_to_screen("Downloading transaction data from DSE...")
        dseresult = super(self.__class__,self).download_html(DSE_LATEST_URL)

        if len(dseresult) <= 0:
            print("ERROR! There was an error fetching data from server.")
            return

        log_to_screen("Download completed. Parsing data...")
        soup = BeautifulSoup(self._RE_HTML_BODY_SANITIZER.sub('<body>', dseresult))
        headtr = soup.body.table.tr.findAll('b')

        output = StringIO.StringIO()
        csvformatter = csv.writer(output)

        if emit_csv_header:
            heads = []
            for h in headtr:
                heads.append(str(h.contents[0]).replace('&nbsp;', '').strip())

            heads.insert(1, "Date")
            heads.insert(2, "Time")
            csvformatter.writerow(heads)

        total_companies, inactive_companies = 0, 0
        all_rows = []
        data = soup.body.table.findAll('tr')[1:]
        for row in data:
            row = row.findAll('td')[1:]
            d = [row[0].a.contents[0], last_update.strftime(r"%Y-%m-%d"), last_update.strftime(r"%H:%M:%S")]
            for col in row[1:]:
                d.append(col.find(text=True))

            total_companies += 1
            if (d[-1] == '0') and (filter_inactive_companies):
                inactive_companies += 1
            else:
                all_rows.append(d)

        log_to_screen("Completed analysis")
        log_to_screen("Quick stats:")
        log_to_screen("\tTotal Companies: " + str(total_companies))
        log_to_screen("\tActive Companies: " + str(total_companies - inactive_companies))
        log_to_screen("\tInactive Companies: " + str(inactive_companies))

        csvformatter.writerows(all_rows)
        csvdata = output.getvalue()
        output.close()

        log_to_screen("CSV data written to " +  os.path.basename(csvname))

        with open(csvname, 'wb') as f:
            f.write(csvdata)

        dump_records(all_rows)


class CSEHandler(AbstractStockExchangeHandler):
    _RE_CSE_DATE = re.compile(r'Date: '
                           r'([a-zA-Z]{3})\s*(\d{2})\s*(\d{4})\s*(\d{1,2}):(\d{1,2})(AM|PM)')
    _RE_CSE_TABLE_DATA = re.compile(r'^\s*(\w+).*?'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(-{0,1}\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+'
                           '(\d+\.{0,1}\d*)\s+', re.MULTILINE)

    def __init__(self):
        super(self.__class__,self).__init__("cse")

    def process(self):
        log_to_screen("Downloading transaction data from CSE...")
        cse_html_page = super(self.__class__,self).download_html(CSE_LATEST_URL)
        last_update = datetime.datetime.now()

        if len(cse_html_page) <= 0:
            print("ERROR! There was an error fetching data from server.")
            return

        log_to_screen("Download completed. Parsing data...")
        soup = BeautifulSoup(cse_html_page)
        precontents = soup.body.findAll('pre')

        sdate = list(self._RE_CSE_DATE.search(precontents[0].contents[0]).groups())
        for i in [1, 3, 4]:
            if len(sdate[i]) == 1:
                sdate[i] = '0' + sdate[i]
        sdate = ' '.join(sdate)
        last_update = datetime.datetime.strptime(sdate, r'%b %d %Y %I %M %p')
        log_to_screen("CSE Last updated on " + last_update.isoformat())

        csvname =  (csv_filename != "") and csv_filename or super(self.__class__,self).get_filename(last_update)

        output = StringIO.StringIO()
        csvformatter = csv.writer(output)

        if emit_csv_header:
            heads = ['Company', 'Date', 'Time', 'Open', 'High', 'Low', 'Close',
                     'Prev. Close', 'Difference', 'Trades', 'Volume',]
            csvformatter.writerow(heads)

        all_rows = []
        contents = precontents[1].contents[0].split('\n')
        total_companies, inactive_companies = 0, 0
        for content in contents:
            try:
                data = list(self._RE_CSE_TABLE_DATA.search(content).groups())
                total_companies += 1
                if (data[-1] == '0') and (filter_inactive_companies):
                    inactive_companies += 1
                    continue
                data.insert(1, last_update.strftime(r"%Y-%m-%d"))
                data.insert(2, last_update.strftime(r"%H:%M:%S"))
                sss = data[-1]
                all_rows.append(data)
            except:
                pass

        log_to_screen("Completed parsing")
        log_to_screen("Quick stats:")
        log_to_screen("\tTotal Companies: " + str(total_companies))
        log_to_screen("\tActive Companies: " + str(total_companies - inactive_companies))
        log_to_screen("\tInactive Companies: " + str(inactive_companies))

        csvformatter.writerows(all_rows)
        csvdata = output.getvalue()
        output.close()

        with open(csvname, 'wb') as f:
            f.write(csvdata)

        log_to_screen("CSV data written to " +  os.path.basename(csvname))
        dump_records(all_rows)

def main():
    parse_options()
    show_banner()

    if not  os.path.isdir(CSV_OUTPUT_DIR):
        os.mkdir(CSV_OUTPUT_DIR)

    handler = DSEHandler() if process_dse_data else CSEHandler()
    handler.process()

if __name__ == '__main__':
  main()