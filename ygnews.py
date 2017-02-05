#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
twitter news download module
"""

from twitter import *
import re, time, os, sys
import json
import argparse
from ygsecrets import tw_access_key, tw_access_secret, tw_consumer_key, tw_consumer_secret
import ygdb
import ygimport

class ygnews(object):
    """
    this class handles connecting to twitter and receiving tweets
    saves the data to the tweets table as raw json text
    or optionally logs to file

    nodes are identified by their ip and a numeric thread id
    this is used to get feeds for this particular node from the db

    the application itself is currently single threaded
    this seems to work with the given number of feeds
    and logging to file

    when saving to the db it would be reasonable to parallelize
    each individual application instance
    """
    def __init__(self, ip, thread, log=None, feedlist=None):
        """
        creates twitter helper object
        and database connection
        optionally define a log file ('-' is stdout)
        optionally define an input list of feeds
        """
        self.twitter = Twitter( 
            auth = OAuth(
                tw_access_key,
                tw_access_secret,
                tw_consumer_key,
                tw_consumer_secret
            )
        )
        self.log = log
        self.feedlist = feedlist 
        self.ip = ip
        self.thread = thread 

    def poll(self, feedlist=None):
        """
        rotate through list of feeds and grab data from them
        reads feeds sequentially 
        """
        feeds = []
        if feedlist is None:
            feedlist = self.feedlist

        if feedlist is None:
            feeds = self._get_feeds_from_db()
        elif feedlist == '-' or os.path.isfile(feedlist):
            feeds = self._get_feeds_from_file(feedlist)
        else:
            raise(Exception("invalid feedlist identifier - is it a file?"))

        if self.log is not None:
            for user in feeds:
                self._log_status_to_file(user)
        else:
            for user in feeds:
                self._log_status_to_db(user)

    def _get_feeds_from_file(self, feedlist):
        """
        reads feed urls from a file one per line

        the file should have the format of:
            nytimes, "New York Times"
        where the feed's screen name is the first item 
        followed by a non-alphanumeric character or end of line

        returns list of screen names
        """
        feeds = []
        if feedlist == '-': 
            fh = sys.stdin
        else:
            fh = open(feedlist,'r')

        for feed in fh:
            f = re.match(r'(\w+)', feed)
            if f is None:
                continue
            feeds.append(f.group(1))

        if fh != sys.stdin:
            fh.close()

        return feeds

    def _get_feeds_from_db(self):
        """
        uses ygdb to get a list of feeds
        for this specific instance
        """
        feeds = []
        conn = ygdb.conn()
        get = conn.cursor()
        get.execute(
            "select user from feeds where ip=%s and thread=%s", 
            (self.ip, self.thread)
        )
        for row in get:
            feeds.append(row[0])
        get.close()
        conn.close()
        return feeds

    def _log_status_to_db(self, user):
        """
        uses ygimport to save the status directly to the db
        """
        results = self.twitter.statuses.user_timeline(screen_name = user)
        tweet = {'user': user}
        for status in results:
            tweet['lines'] = json.dumps(status)
            ygimport.save(tweet, self.ip, self.thread)

    def _log_status_to_file(self, user):
        """
        gets timeline status for a given user
        saves the timeline to a file
        use ygimport.py to import the data from the log to the db
        """

        log = None
        if self.log == '-': 
            log = sys.stdout
        elif self.log is not None:
            log = open(self.log,'a')

        log.write("\nFEED {}\n".format(user))

        results = self.twitter.statuses.user_timeline(screen_name = user)
        usersaved = False
        for status in results:
            # to reduce space only save user part of status once per run
            try:
                if usersaved: del(status['user'])
                usersaved = True
            except:
                pass
            log.write(json.dumps(status, indent=2))
            log.write("\n")

        log.write("\nEND {}\n".format(user))

        if self.log != '-' and log is not None:
            log.close()

        time.sleep(2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=
            "Poll a list of twitter feeds for timeline status.\n"
            "By default get feed list from db and save directly to db."
    )
    parser.add_argument('--ip',required=True,help='ip (or localhost) for this node')
    parser.add_argument('--thread',required=True,type=int,help="thread number for this node")
    parser.add_argument('--feeds',help='optional file name containing feeds one per line (- for stdin)')
    parser.add_argument('--log',help='optional name of log file to save data to (- for stdout)')
    args = parser.parse_args()
    news = ygnews(
        args.ip,
        args.thread,
        log=args.log,
        feedlist=args.feeds
    )
    news.poll()

