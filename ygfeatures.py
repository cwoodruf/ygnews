#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
extracts data from json stored in the tweets table and
saves relations between links, users and tweets
does some basic word processing for tweets

did not find stemming or part of speech tagging to be useful
for clustering of these tweets

news feeds are unusually clean linguistic sources and tend to 
produce relatively simple grammar in a "headline" style

concatenate text from subtweets with the tweet text 
"""
from ygcursors import ygcursors
import yglog
import sys
import json
import re
import time
import traceback
import argparse

class ygfeatures(ygcursors):
    """
    takes care of unpacking tweet data and processing it
    saves output to the features, links, tweetwords and tweetbigrams tables
    this is more than we actually use but makes it easier to do analysis after
    """
    def __init__(self, ip=None, thread=None):
        """
        constructor optionally sets ip and thread 
        to identify instance when searching for tweets
        """
        super(ygfeatures, self).__init__()
        self.ip = None

        if ip is not None:
            icheck = re.match(r'[\w\.\-]+', ip)
            if icheck is not None:
                self.ip = ip
        try:
            self.thread = int(thread)
        except:
            self.thread = None

    def reset_features(self):
        """
        clears out several tables and resets scanned in tweets table
        """
        rem = self.getcursor()
        rem.execute("delete from features")
        rem.execute("delete from tweetwords")
        rem.execute("delete from tweetbigrams")
        rem.execute("delete from links")
        rem.execute("update tweets set scanned=0")
        rem.close()
        self._commit()

    def get_stop_words(self):
        """
        retrieves the stop words from stopwords
        returns a dict
        """
        get = self.getcursor()
        get.execute("select lower(term) from stopwords")
        stopwords = {}
        for row in get:
            term = row[0]
            stopwords[term] = True
        get.close()
        return stopwords
        
    def save_entities(self, data):
        """
        extracts the entities section of data and updates links
        """
        if not 'entities' in data: return
        links = []
        if 'urls' in data['entities']:
            for urldata in data['entities']['urls']:
                links.append((data['id'],urldata['url'],'urls'))
        if 'media' in data['entities']:
            for mediadata in data['entities']['media']:
                links.append((data['id'],mediadata['url'],'media'))

        if 'retweeted_status' in data:
            links.append((data['id'],data['retweeted_status']['id_str'],'retweet'))

        if 'quoted_status' in data:
            links.append((data['id'],data['quoted_status']['id_str'],'quote'))

        yglog.vprint("links", links)

        if len(links) == 0: return

        ins = self.getcursor()
        ins.executemany(
            "insert ignore into links (id,link,source) values (%s,%s,%s) ",
            links
        )
        ins.close()
        self._commit()
        
    def save_features(self, features):
        """
        saves specific items from data listed in features
        """
        fieldnames = ",".join(features.keys())
        placeholders = ",".join(["%s" for f in range(len(features))])
        fieldvals = tuple(features.values())
        upd = self.getcursor()
        upd.execute(
            "insert ignore into features ({}) values ({})".format(fieldnames,placeholders), 
            fieldvals
        )
        upd.close()
        self._commit()
        
    def save_wordstats(self, tweetid, grams):
        """
        given a dict of tuples lists by table
        insert them all into the db
        """
        for table, termdict in grams.iteritems():
            termlist = []
            for term, num in termdict.iteritems():
                termlist.append((tweetid, term, num))
            ins = self.getcursor()
            yglog.vprint("saving to",table)
            yglog.vprint(termlist)
            ins.executemany(
                "replace into {} (id, term, num) values (%s,%s,%s) ".format(table),
                termlist
            )
            ins.close()
            self._commit()
                
        
    def extract_and_save_features(self, data, stopwords):
        """
        does some basic cleanup of the tweet text 
        saves a bag of words list for each tweet
        these include emails, user ids and hash tags
        also makes and saves bigrams
        
        for now, am ignoring odd characters in words
        """
        tweetid = data['id']
        rawtext = data['text'].encode('ascii','replace')

         # treat quotes and retweets as if they were part of the original tweet
        if 'quoted_status' in data:
            if 'text' in data['quoted_status']:
                rawtext += " "
                rawtext += data['quoted_status']['text'].encode('ascii','replace')
        if 'retweeted_status' in data:
            if 'text' in data['retweeted_status']:
                rawtext += " "
                rawtext += data['retweeted_status']['text'].encode('ascii','replace')
        yglog.vprint(rawtext)
        words = rawtext
        words = re.sub(r'https?://\S*','',words)
        words = re.sub(r'&amp;','and',words)
        words = re.sub(r'&quot;','"',words)
        words = re.sub(r'&nbsp;',' ',words)
        words = re.sub(r'"', ' ', words)
        words = re.sub(r"'", ' ', words)
        words = re.sub(r'[!?\.]+',' ',words) # may want to tag end of sentence? - clash with 'replace's ?s
        words = re.sub(r'[,;:\-\~\$\%\^\&\*\(\)\{\}\[\]\|\\<>/]', ' ', words)
        words = re.sub(r'\s+', ' ', words)
        wordlist = words.split()
        yglog.vprint(tweetid,wordlist)

        tweetbigrams = {}
        tweetwords = {}
        savedwords= []
        prevword = None

        for word in wordlist:
            if word in stopwords: continue

            savedwords.append(word)

            if prevword is not None:
                bigram = "{} {}".format(prevword, word)
                if bigram not in tweetbigrams: tweetbigrams[bigram] = 0
                tweetbigrams[bigram] += 1

            if word not in tweetwords: tweetwords[word] = 0
            tweetwords[word] += 1
            prevword = word

        self.save_wordstats(data['id'], {'tweetbigrams':tweetbigrams, 'tweetwords':tweetwords})

        features = {
            'id': data['id'],
            'user': data['user'],
            'rawtext': rawtext,
            'words': json.dumps(savedwords),
            'lang': data['lang'],
            'favorite_count': data['favorite_count'],
            'retweet_count': data['retweet_count'],
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S', 
                    time.strptime(data['created_at'],'%a %b %d %H:%M:%S +0000 %Y'))
        }
        yglog.vprint(features)
        self.save_features(features)

    def set_scanned(self, data):
        upd = self.getcursor()
        upd.execute("update tweets set scanned=1 where id=%s", (data['id'],))
        upd.close()
        self._commit()

    def summarize(self):
        """
        rebuilds the words and bigrams tables based on individual tweet data
        generally this is faster than doing the updates individually

        this would work better as a stored procedure
        """
        replace = self.getcursor()
        replace.execute(
            "delete from words"
        )
        replace.execute(
            "insert into words (term, num) select term,count(*) from tweetwords group by term"
        )
        replace.execute(
            "delete from bigrams"
        )
        replace.execute(
            "insert into bigrams (term, num) select term,count(*) from tweetbigrams group by term"
        )
        replace.execute(
            "update features a,tweets b set a.user=b.user where a.id=b.id and a.user is null"
        )
        replace.execute(
            "update features set combined_count=retweet_count+favorite_count "
            "where combined_count is null"
        )
        replace.execute(
            "update users a,(select user,avg(combined_count) cav "
            "from features group by user) b set a.combined_av=b.cav where a.screen_name=b.user"
        )
        replace.close()
        self._commit()

    def scan_tweets(self, clean=False):
        """
        looks in tweets for tweets where scanned = 0

        will limit itself to look for tweets assigned to a specific ip or thread
        if these are defined in the constructor

        extracts features from the tweets such as favorite and retweet counts
        maps links and users to tweets
        manipulates the words in various ways
        """
        if clean: self.reset_features()
        ipquery = ""
        if self.ip is not None:
            ipquery += " and processing_ip='{}'".format(self.ip)
        if self.thread is not None:
            ipquery += " and processing_thread='{}'".format(self.thread)
        try:
            get = self.getcursor()
            get.execute(
                "select user, raw from tweets where scanned = 0 {}".format(ipquery)
            )
            stopwords = self.get_stop_words()
            tweetcount = 0
            for row in get:
                user, raw = row
                data = json.loads(raw)
                data['user'] = user # effectively truncates the existing user data
                self.save_entities(data)
                self.extract_and_save_features(data, stopwords)
                self.set_scanned(data)
                tweetcount += 1

            yglog.vprint("processed",tweetcount,"tweets")
            if tweetcount > 0: self.summarize()

        except Exception as e:
            sys.stderr.write("ygfeatures.scan_tweets error: {}\n".format(e))
            traceback.print_tb(sys.exc_traceback)
        finally:
            get.close()
            

if __name__ == '__main__':

    parser = argparse.ArgumentParser("scan tweets table for new tweets and extract NLP features")
    parser.add_argument('--ip',help="optional ip to find relevant tweets for this host")
    parser.add_argument('--thread',help="optional thread number to find relevant tweets for this instance")
    parser.add_argument('--clean',action='store_true',help="delete data from features tables")
    parser.add_argument('--verbose',action='store_true',help="print lots of debug messages")
    args = parser.parse_args()

    yglog.verbose = args.verbose
    with ygfeatures(ip=args.ip, thread=args.thread) as feat:
        feat.scan_tweets(clean=args.clean)

