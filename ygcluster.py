#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
clustering module for the news service
given that we don't know in advance what the topics are likely to be
chose dbscan as the algorithm to discover topics
"""
from ygcursors import ygcursors
import yglog
import json
import math
import argparse
import datetime

class ygdbscan(ygcursors):
    """
    run dbscan on the related pair data in the similarity table
    can display cluster contents in various ways
    """
    def __init__(self, args):
        super(ygdbscan, self).__init__()
        self.clusters = {}     # what we build with dbscan
        self.clustered = {}
        self.noise = {}        # not really used but contains items with few neighbours
        self.lastcluster = -1  # identifier for current cluster
        self.epsilon = args.epsilon # neighbours must be more similar than this
        self.minsz = args.minsz     # smallest number of neighbours allowed
        self.daysback = args.daysback # how far back to look for root tweets

    def inc_cluster(self, tweetid):
        self.lastcluster = tweetid
        self.clusters[self.lastcluster] = {}
        self.add2cluster(tweetid)

    def add2cluster(self, tweetid):
        yglog.vprint("cluster",self.lastcluster,"now has",tweetid)
        self.clusters[self.lastcluster][tweetid] = True
        self.clustered[tweetid] = True

    def in_cluster(self, tweetid):
        if tweetid in self.clustered: return True
        return False

    def get_neighbours(self, id1):
        if id1 not in self.pairs: 
            raise(Exception("ygdbscan.get_neighbours: missing {} in pairs".format(id1)))
        candidates = {}
        for tweetid, sim in self.pairs[id1].iteritems():
            if sim >= self.epsilon:
                candidates[tweetid] = sim

        neighbours = sorted(candidates,key=candidates.__getitem__,reverse=True)
        neighbours.append(id1)
        return neighbours

    def dbscan(self):
        """
        main engine of the class: makes clusters based on closeness of neighbours
        """
        seen = {}

        yglog.vprint("searching",len(self.tweetids),"tweets")
        for id1 in self.tweetids:
            if id1 in seen: 
                continue
            seen[id1] = True
            neighbours = self.get_neighbours(id1)
            if len(neighbours) < self.minsz:
                # yglog.vprint(id1,"has less than",self.minsz,"neighbours")
                self.noise[id1] = True
            else:
                self.inc_cluster(id1)
                neighbourlist = neighbours
                while len(neighbourlist) > 0:
                    n = neighbourlist.pop()
                    if n in seen: continue
                    seen[n] = True
                    newneighbours = self.get_neighbours(n)
                    if len(newneighbours) <= self.minsz:
                        continue
                    for nn in newneighbours:
                        if nn not in neighbourlist:
                            neighbourlist.append(nn)
                    if not self.in_cluster(n):
                        self.add2cluster(n)

    def run(self):
        """
        initializes data and runs dbscan algorithm 
        """
        self.tweetids = self.initpairs(daysback=self.daysback)
        self.dbscan()
        self.get_clustertweets()
        self.get_stats()

    def get_interesting(self, minscore=None, scorekey='maxscores'):
        """
        given a minimum score and key to search in return the top tweets for each cluster found
        """
        try:
            stats = self.stats
            clustertweets = self.clustertweets
        except:
            return None

        scores = stats[scorekey]
        if minscore is None:
            sortscores = sorted(scores)
            N = len(sortscores)
            if N >= 20: cutoff = int(math.floor(N * 0.9))
            elif N >= 10: cutoff = int(math.floor(N* 0.8))
            else: cutoff = int(math.floor(N* 0.5))
            minscore = sortscores[cutoff]
            yglog.vprint("cutoff",cutoff,"N",N,"minscore",minscore,"from",sortscores)

        interesting = {}
        for clidx, score in enumerate(scores):
            if score >= minscore:
                clusterid = stats['clusterids'][clidx]
                twidx = stats['besttweetidx'][clidx]
                interesting[clusterid] = clustertweets[clusterid][twidx]
        return interesting

    def get_toptweet(self):
        """
        if get_stats was run, get the data for the top tweet
        """
        try:
            stats = self.stats
        except:
            return None
        return self.get_tweet(self.stats['toptweet'])

    def get_tweet(self, tweetid):
        """
        grab features for a given tweet id from the features table
        """
        get = self.getcursor()
        get.execute(
            "select created_at,id,rawtext,combined_count,retweet_count,favorite_count,user "
            "from features where id=%s", 
            (tweetid,)
        )
        row = get.fetchone()
        get.close()
        created_at, tweetid, rawtext, combined_count, retweet_count, favorite_count, screen_name = row
        tweet = {
            'created_at': '{:%Y-%m-%d %H:%M:%S}'.format(created_at),
            'id': tweetid,
            'rawtext': rawtext,
            'combined_count': combined_count,
            'retweet_count': retweet_count,
            'favorite_count': favorite_count,
            'screen_name': screen_name,
        }
        return tweet

    def get_stats(self):
        """
        generates a group of ordered lists with stats on the clusters
        these are used to find "interesting" clusters and tweets
        """
        try:
            clustertweets = self.clustertweets
        except:
            raise(Exception("ygdbscan.get_stats: need to run dbscan first!"))
        maxscores = []
        avscores = []
        clustersz = []
        besttweets = []
        besttweetidx = []
        for cl,tweets in clustertweets.iteritems():
            scores = []
            tweetids = []
            for tweet in tweets:
                scores.append(tweet['combined_count'])
                tweetids.append(tweet['id'])

            maxscore = max(scores)
            maxidx = scores.index(maxscore)
            besttweet = tweetids[maxidx]
            n = len(tweets)
            avscore = float(sum(scores))/float(n)

            maxscores.append(maxscore)
            avscores.append(avscore)
            clustersz.append(n)
            besttweets.append(besttweet)
            besttweetidx.append(maxidx)
            
        clusterids = clustertweets.keys()
        bestindex = maxscores.index(max(maxscores))
        topcluster = clusterids[bestindex]
        toptweet = besttweets[bestindex]
        self.stats = {
                'clusterids': clusterids,
                'maxscores': maxscores,
                'avscores': avscores,
                'clustersz': clustersz,
                'besttweets': besttweets,
                'besttweetidx': besttweetidx,
                'topcluster': topcluster,
                'toptweet': toptweet
        }
                    
    def get_clusterterms(self, limit):
        """
        what are the most important words for this cluster?
        """
        # get all terms for all clusters
        clusterterms = {}
        orderedterms = {}
        for cluster,tweets in self.clusters.iteritems():
            clusterterms[cluster] = {}
            for rootid in tweets:
                neighbours = self.get_neighbours(rootid)
                for tweetid in neighbours:
                    get = self.getcursor()
                    get.execute(
                        "select term,num from tweetwords "
                        "where id=%s",
                        (tweetid,)
                    )
                    for row in get:
                        term, num = row
                        if term not in clusterterms[cluster]:
                            clusterterms[cluster][term] = 0
                        clusterterms[cluster][term] += num
                    get.close()
            # ensure we are sorted by frequency
            orderedterms[cluster] = sorted(clusterterms[cluster],
                            key=clusterterms[cluster].__getitem__,reverse=True)
        # get the short list
        candidates = {}
        for cluster,terms in orderedterms.iteritems():
            candidates[cluster] = {}
            count = limit if len(terms) >= limit else len(terms)
            for i in xrange(count):
                candidates[cluster][terms[i]] = clusterterms[cluster][terms[i]]
                
        self.clusterterms = candidates
                    
    def get_clustertweets(self):
        """
        get tweet data for clusters
        """
        clustertweets = {}
        for cl,tweets in self.clusters.iteritems():
            clustertweets[cl] = []
            for rootid in tweets:
                yglog.vprint("root",rootid,"for cluster",cl)
                neighbours = self.get_neighbours(rootid)
                for tweetid in neighbours:
                    yglog.vprint(rootid,"neighbour",tweetid)
                    get = self.getcursor()
                    get.execute(
                        "select created_at,rawtext,combined_count,retweet_count,"
                            "favorite_count,user "
                        "from features where id=%s ",
                        (tweetid,)
                    )
                    row = get.fetchone()
                    get.close()
                    try:
                        root_similarity = self.pairs[rootid][tweetid]
                    except:
                        root_similarity = None
                    tweet = list(row)
                    created_at = '{:%Y-%m-%d %H:%M:%S}'.format(tweet.pop(0))
                    clustertweets[cl].append({
                        'root': rootid,
                        'root_similarity': root_similarity,
                        'id': tweetid,
                        'words': tweet.pop(0),
                        'combined_count': tweet.pop(0),
                        'retweet_count': tweet.pop(0),
                        'favorite_count': tweet.pop(0),
                        'screen_name': tweet.pop(0),
                        'created_at': created_at,
                    })
        self.clustertweets = clustertweets

    def initpairs(self, daysback=2):
        """
        loads all pairs from similarity into memory 
        this is used to determine if two tweets are related
        score is sum of jaccard similarity plus number of links shared
        set daysback to expand number of pairs used for cluster
        """
        getpairs = self.getcursor()
        getpairs.execute(
            "select min(id) from features where created_at > now() - interval %s day",
            (daysback,)
        )
        row = getpairs.fetchone()
        minid = row[0]
        yglog.vprint("starting with id",minid)
        getpairs.execute(
            "select id1,id2,jaccard+links sim from similarity where id1 > %s",
            (minid,)
        )
        pairs = {}
        i = 0
        for row in getpairs:
            id1,id2,similarity = row
            i += 1
            if id1 not in pairs:
                pairs[id1] = {}
            if id2 not in pairs:
                pairs[id2] = {}
            pairs[id1][id2] = similarity
            pairs[id2][id1] = similarity
        yglog.vprint("found",i,"rows in similarity")
        getpairs.close()
        self.pairs = pairs
        yglog.vprint(len(self.pairs.keys()),"keys in self.pairs")
        return self.pairs.keys()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        "use dbscan algorithm to make a group of clusters from processed tweet data"
    )
    parser.add_argument('--epsilon',type=float,required=True,help="smallest similarity score to use")
    parser.add_argument('--minsz',type=int,required=True,help="minimum number of neighbours to have to use tweet")
    parser.add_argument('--verbose',action='store_true',help="show debug messages")
    parser.add_argument('--clusters',action='store_true',help="json dump cluster tweetids")
    parser.add_argument('--tweets',action='store_true',help="json dump tweets in clusters")
    parser.add_argument('--stats',action='store_true',help="json dump cluster stats")
    parser.add_argument('--best',action='store_true',help="json dump best cluster and tweet")
    parser.add_argument('--interesting',action='store_true',help="json dump top tweets")
    parser.add_argument('--keywords',type=int,help="json dump top N keywords for clusters")
    parser.add_argument('--daysback',type=int,default=2,help="base clusters on tweets newer than this")
    args = parser.parse_args()
    yglog.verbose = args.verbose

    with ygdbscan(args) as dbscan:
        dbscan.run()
        if args.clusters: 
            print json.dumps(dbscan.clusters, indent=4)
        if args.tweets:
            print json.dumps(dbscan.clustertweets, indent=4)
        if args.stats:
            print json.dumps(dbscan.stats, indent=4)
        if args.best:
            print json.dumps({
                'clusterid': dbscan.stats['topcluster'],
                'tweetid': dbscan.stats['toptweet'],
                'tweetdata': dbscan.get_toptweet(),
            }, indent=4)
        if args.interesting:
            print json.dumps(dbscan.get_interesting(), indent=4)
        if args.keywords > 0:
            dbscan.get_clusterterms(args.keywords)
            print json.dumps(dbscan.clusterterms, indent=4)

