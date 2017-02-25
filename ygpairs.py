#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
find pairs of tweets that are relatively popular and fill pairs table with them
because the number of items to compare can grow exponentially only select the top N
tweets per source 

the way this works is:

- first select a short list of tweets we are interested in based on the popularity of the tweet
- generate an upper triangular matrix of pairs to check saving to the pairs table
- nodes can assign themselves a group of pairs to check - there is no manager process

"""
from ygcursors import ygcursors
import yglog
import sys
import traceback
import re
import argparse
import math

DEF_THRESHOLD = 0.5 # should be 0.0 to < 1.0
SAVE_THRESHOLD = 10000 # how many pairs to save at a time
MAX_TWEETS = 2000 # total maximum number of tweets to select from all sources
PAIR_COUNT = 10000 # default number of pairs to return when a node requests a sample

def usage(parser):
    parser.print_usage()

class ygpairs(ygcursors):
    """
    class to set up and maintain a schedule of work
    
    the bulk of the work in the system is likely to be doing comparisons of tweets
    this class implements the mechanics of identifying pairs to consider
    the number of tweets in a day is too large to process so we use
    a metric to decide which tweets to consider
    this is the self.threshold property of the class
    """

    def __init__(self, threshold=None, maxtweets=MAX_TWEETS, save=SAVE_THRESHOLD):
        """
        by default create shared db connection
        set thresholds for accepting tweets

        the threshold variable is based on features.combined/users.combined_av 
        which is the sum of retweet_count and favorite_count/ the average for that user

        the threshold is arbitrary and exists to reduce 
        useless processing of data people aren't likely to be interested in

        using a single threshold reduces likelihood of redundancy
        if we consider ids in order and only pair ids greater than the current id

        maxtweets limits the number of tweets we'll use for comparison
        we pick the top N for each user up to a proportion based on their over threshold tweets
        """
        super(ygpairs, self).__init__()
        if threshold is None:
            self.threshold = DEF_THRESHOLD
        else:
            self.threshold = float(threshold)

        self.maxtweets = maxtweets
        self.save_threshold = save

    @staticmethod
    def get_pairs(ip,thread,paircount=None):
        """
        class method that claims a group of pairs for a specific ip,thread
        returns the list of pairs to process
        """
        if paircount is None: limit = PAIR_COUNT
        else: limit = int(paircount)

        if limit <= 0: return []
        yglog.vprint("get_pairs getting",limit,"pairs for",ip,thread)

        conn = ygcursors()
        get = conn.getcursor()
        get.execute(
            "select id1,id2 from pairs where ip is null and processed is null "
            "order by id1,id2 limit %s",
            (limit,)
        )
        upd = conn.getcursor()
        pairs = []
        for row in get:
            id1, id2 = row
            upd.execute(
                "update pairs set ip=%s,thread=%s,processed=now() where id1=%s and id2=%s",
                (ip, thread, id1, id2)
            )
            pairs.append((id1,id2))
        upd.close()
        conn._commit()
        conn.closedb()
        return pairs
            
    def cleanup_pairs(self, cutoff=None):
        """
        removes pairs that have been processed
        """
        rem = self.getcursor()
        if cutoff is None:
            rem.execute("drop table pairs")
            rem.execute("create table pairs (like pairs_template)")
        else:
            isdate = re.match(r'\d\d\d\d-\d\d-\d\d', cutoff)
            if isdate is None: raise(Exception("cleanup_pairs: bad date format!"))
            rem.execute("delete from pairs where processed < %s", cutoff)
        rem.close()
        self._commit()

    def unprocessed_pairs(self, cutoff=None):
        """
        find jobs that haven't been started yet
        """
        get = self.getcursor()
        if cutoff is None: 
            get.execute(
                "select id1, id2 from pairs where processed is null",
                cutoff
            )
        else:
            isdate = re.match(r'\d\d\d\d-\d\d-\d\d', cutoff)
            if isdate is None: raise(Exception("unprocessed_pairs: bad date format!"))
            get.execute(
                "select id1, id2 from pairs where processed is null and added < %s",
                cutoff
            )

    def insert_pairs(self, pairs):
        """
        non-destructively inserts an ordered pair of ids into pairs
        """
        if len(pairs) == 0: return
        yglog.vprint("adding",len(pairs),"pairs")
        ins = self.getcursor()
        ins.executemany(
            "insert ignore into pairs (id1,id2,added) values (%s,%s,now())",
            pairs
        )
        ins.close()
        self._commit()
        
    def add_pairs(self, th=None, mt=0):
        """
        grab all ids from features using combined_count thresholds
        these can be temporarily set
        optionally set the threshold and maximum tweets to process
        """
        if th is not None: 
            try:
                threshold = float(th)
            except:
                threshold = self.threshold
        else:
            threshold = self.threshold

        try:
            # want to get the top N tweets per user
            get = self.getcursor()
            yglog.vprint("threshold",threshold)
            get.execute(
                "select user,count(*) from user_features "
                "where combined_count/combined_av > %s "
                "group by user", (threshold,)
            )
            alltweets = 0
            tweetcounts = {}
            for row in get:
                user, tweetcount = row
                yglog.vprint(user, tweetcount)
                tweetcounts[user] = int(tweetcount)
                alltweets += int(tweetcount)
            get.close()

            maxtweets = mt if mt > 0 else self.maxtweets
            ids = []
            upd = self.getcursor()
            upd.execute("update features set selected=null where selected is not null")
            upd.close()
            self._commit()
            for user, tweetcount in tweetcounts.iteritems():
                limit = math.ceil(float(maxtweets) * float(tweetcount)/float(alltweets))
                yglog.vprint("user",user,"limit",limit,"out of",maxtweets,"all",alltweets,"count",tweetcount)
                getids = self.getcursor()
                getids.execute(
                    "select id from features where user=%s "
                    "order by combined_count desc limit %s",
                    (user, limit)
                )
                upd = self.getcursor()
                for row in getids:
                    ids.append(int(row[0]))
                    upd.execute("update features set selected=date(now()) where id=%s", (row[0],))
                getids.close()
                self._commit()
                upd.close()

            sorted(ids)
            pairs = []
            paircount = 0
            for i in xrange(len(ids)):
                for j in xrange(i+1,len(ids)):
                    pairs.append((ids[i], ids[j]))
                    paircount += 1
                    if len(pairs) >= self.save_threshold:
                        self.insert_pairs(pairs)
                        yglog.vprint("pairs now", paircount)
                        pairs = []
            yglog.vprint("pairs at end", paircount)
            self.insert_pairs(pairs)
        except Exception as e:
            sys.stderr.write("all_pairs error: {}\n".format(e))
            traceback.print_tb(sys.exc_traceback)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        "generate a set of tweet pairs to check for similarity"
    )
    parser.add_argument(
        "--maxtweets",type=int,
        help="maximum number of tweets to use as starting point",default=MAX_TWEETS)
    parser.add_argument(
        "--threshold",type=int,
        help="combined_count/combined_av threshold",default=DEF_THRESHOLD)
    parser.add_argument("--clean",action='store_true',help="delete pairs table before regenerating")
    parser.add_argument("--verbose",action='store_true',help="print lots of debug info")
    args = parser.parse_args()

    yglog.verbose = args.verbose
    pairs = ygpairs(
        threshold=args.threshold,
        maxtweets=args.maxtweets
    )
    if args.clean: pairs.cleanup_pairs()
    pairs.add_pairs()

