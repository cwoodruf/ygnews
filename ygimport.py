#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
In stand alone mode this is a relatively simple script that reads a log 
from ygnews.py and imports twitter data into the tweets table in the db.

Also used by the ygnews module to save directly to the db.
"""
import ygdb
import sys
import os
import re
import json

conn = None

NOIP = 'ygimport'
NOTHREAD = -1

def save(tweet,ip=NOIP,thread=NOTHREAD):
    """
    saves a tweet dictionary to the tweets table
    source could be a relatively simple log of tweets as they arrived
    in which case "lines" is an array of the lines which would need to be joined
    
    this may be run in a multithreaded context hence the sys.stderr.write calls
    which print atomically
    """
    if 'user' not in tweet:
        sys.stderr.write("ygimport.save: missing user!")
        return False
    if 'lines' not in tweet:
        sys.stderr.write("ygimport.save: missing tweet lines!")
        return False

    global conn
    local = False
    if conn is None: 
        local = True;
        conn = ygdb.conn()

    ins = conn.cursor()
    try:
        raw = "".join(tweet['lines'])

        # want to automatically abort if any of this fails ...
        data = json.loads(raw)
        tweetid = data['id']
        created = data['created_at']
        ins.execute(
            "replace into tweets "
            "(id,user,imported,created,raw,import_ip,import_thread) values "
            "(%s,%s,now(),%s,%s,%s,%s)",
            (tweetid, tweet['user'], created, raw, ip, thread)
        )
        if 'user' in data:
            user = data['user']
            ins.execute(
                "replace into users "
                "(screen_name,favourites_count,followers_count,statuses_count) "
                "values (%s,%s,%s,%s)",
                (
                    user['screen_name'].lower(),
                    user['favourites_count'],
                    user['followers_count'],
                    user['statuses_count']
                )
            )
        ins.close()
        conn.commit()
        saved = True
    except Exception as e:
        sys.stderr.write(
            "ygimport.save error: {} for {} {}".format(
                e,tweetid,ins._last_executed
            )
        )
        saved = False
    finally:
        if local: 
            conn.close()
            conn = None
    return saved
    
def import_tweets(log):
    """
    import the given log file
    it should be filled with raw twitter json interspersed with
    FEED somefeedname
    to identify the source
    Note that the twitter data usuall omits the user to save space
    log should be compatible with something created by ygnews.py
    """
    if not os.path.isfile(log):
        print "need a log file to import"
        sys.exit(1)

    with open(log,'r') as lh:
        started = False
        for line in lh:
            feed = re.match(r'^FEED (\S*)', line)
            if feed is not None:
                user = feed.group(1)
                started = False
                tweet = {'user':user, 'lines':[]}

            start = re.match(r'^{', line)
            if start is not None:
                started = True
                tweet = {'user':user, 'lines':[]}

            if started: tweet['lines'].append(line)

            end = re.match('^}', line)
            if end is not None:
                save(tweet)
                started = False

if __name__ == '__main__':
    ip = NOIP
    thread = NOTHREAD
    try:
        log = sys.argv[1]
    except:
        print "Usage: %s {tweet log file}" % (sys.argv[0],)
        sys.exit(1)

    try:
        ip = sys.argv[2]
        thread = int(sys.argv[3])
    except:
        pass

    conn = ygdb.conn()
    import_tweets(log, thread, ip)
    conn.close()

