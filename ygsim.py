#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
given a list of pairs of tweet ids compare them with each other in various ways:

jaccard - gave most > 0 similarity scores
linkcount - number of common links

other measures take too long to produce (e.g. tfidf)
or seem not so useful for classification in this context (cosine) 
bigrams, stemming and part of speech tagging alone were not found to improve results
have added bigrams to the word list to make comparisons more specific
words and bigrams are weighted

"""
from ygpairs import ygpairs
from ygcursors import ygcursors
import yglog
import json
import traceback
import sys
import argparse
import time

SAVE_ME = 10000 # default number of pairs to collect before inserting
INFINITY = 999

class ygsim(ygcursors):
    """
    handles calculating similarity either using links
    or metrics related to words
    """
    def __init__(self, ip, thread, wait=0.0, savesz=SAVE_ME, epsilon=None):
        super(ygsim, self).__init__()
        self.savesz = savesz
        self.ip = ip
        self.thread = thread
        if epsilon is None: self.epsilon = 0.0
        else: self.epsilon = epsilon
        self.wait = wait
        self.load_words()
        self.load_linkcounts()

    def calc_jaccard (self, list1, list2):
        """
        simple way to compare two featuresets
        count the size of the intersection, then the union
        enhanced by allowing separate weights for different kinds of terms
        result is |intersection|/(|union|-|intersection|)
        unlike a true set multiple matches of the same word count
        """
        intersectiondict = {}
        uniondict = {}
        for f1 in list1:
            for f2 in list2:
                if f1 == f2: 
                    yglog.vprint(f1,'matched',list2[f2],list1[f1])
                    intersectiondict[f2] = list2[f2]
                uniondict[f2] = list2[f2]
                uniondict[f1] = list1[f1]

        intersection = sum(intersectiondict.values())
        union = sum(uniondict.values())

        yglog.vprint("intersection",intersection,"union",union)
        if intersection == union: 
            return INFINITY

        if intersection > union: 
            raise(Exception(
                "jaccard error intersection {} union {}".format(intersection, union)))

        return float(intersection)/(float(union) - float(intersection))

    def load_words(self):
        """
        loads features table words field into memory
        """

        get = self.getcursor()
        get.execute(
            "select id,words from features"
        )
        words = {}
        for row in get:
            tweetid, wordjson = row
            words[tweetid] = json.loads(wordjson)
        self.words = words

    def load_linkcounts(self):
        """
        checks links table to find all tweets sharing links
        saves whole list into memory
        """
        get = self.getcursor()
        get.execute(
            "select id,link from links"
        )
        common = {}
        for row in get:
            tweetid, link = row
            if link not in common:
                common[link] = []
            common[link].append(tweetid)
        get.close()

        linkcounts = {}
        for link in common:
            ids = common[link]
            # always save ids pairs in ascending order
            sorted(ids)
            for i in xrange(len(ids)):
                for j in xrange(i+1,len(ids)):
                    if ids[i] not in linkcounts:
                        linkcounts[ids[i]] = {}
                    if ids[j] not in linkcounts[ids[i]]:
                        linkcounts[ids[i]][ids[j]] = 0
                    linkcounts[ids[i]][ids[j]] += INFINITY
        self.linkcounts = linkcounts

    def get_linkcount(self, id1, id2):
        """
        check for number of common links between two tweets
        always checks ids in ascending order
        """
        if id1 > id2:
            (id1, id2) = (id2, id1)
        if id1 in self.linkcounts:
            if id2 in self.linkcounts[id1]:
                return self.linkcounts[id1][id2]
        return 0

    def compare_two(self, id1, id2):
        """
        compares a pair of tweets and returns one or more similarity scores
        """
        try:
            # originally had many more measures none of which were that useful ...
            if id1 in self.words and id2 in self.words:
                jaccard = self.calc_jaccard(self.words[id1], self.words[id2])
            else:
                jaccard = 0.0
            linkcount = self.get_linkcount(id1,id2)

            return jaccard, linkcount
        except Exception as e:
            sys.stderr.write("ygsim.compare_two error: {} for {} {}\n".format(e,id1,id2))
            traceback.print_tb(sys.exc_traceback)

    def save_similarities(self, similarities):
        """
        save blocks of measured similarities
        """
        if len(similarities) == 0: return
        yglog.vprint("similarities",similarities)
        ins = self.getcursor()
        # jaccard seems to be the only useful one here
        ins.executemany(
            "replace into similarity "
            "(id1,id2,jaccard,links) "
            "values (%s,%s,%s,%s) ",
            similarities
        )
        ins.close()
        self._commit()

    def compare_ids(self, sample):
        """
        given a list of pairs of ids do pairwise comparisons
        save the results in the similarity table
        """
        yglog.vprint("sample",len(sample))
        similarities = []
        for ids in sample:
            (id1, id2) = ids
            yglog.vprint("id1",id1,"id2",id2)
            # most measures aren't working well with this data ...
            jaccard, linkcount = self.compare_two(id1, id2)

            # filter out stuff where there is no significant relationship
            score = linkcount + jaccard
            if (self.epsilon == 0.0 and score > self.epsilon) or \
                    (self.epsilon > 0.0 and score >= self.epsilon): 
                similarities.append((id1,id2,jaccard,linkcount))
                yglog.vprint("similarity",(id1,id2,jaccard,linkcount))

            if len(similarities) >= self.savesz:
                self.save_similarities(similarities)
                similarities = []

        self.save_similarities(similarities)
        upd = self.getcursor()
        for ids in sample:
            id1, id2 = ids
            upd.execute(
                "update features set processed=now() where id=%s",
                (id1,)
            )
        upd.close()
        self._commit()

    def clean_similarities(self):
        """
        delete everything in the similarities table
        """
        yglog.vprint("starting cleanup")
        rem = self.getcursor()
        rem.execute("drop table similarity")
        rem.execute("create table similarity (like similarity_template)")
        rem.execute("update pairs set ip=null,thread=null,processed=null")
        rem.close()
        self._commit()
        yglog.vprint("finished cleanup")

    def scan_pairs(self, maxcount=None, clean=False):
        """
        using the ygpairs static method get_pairs
        do comparisons on each pair and save anything interesting
        """
        if clean:
            self.clean_similarities() # deletes all similarity data

        # sample = ygpairs.get_pairs(self.ip, self.thread)
        pairs = ygpairs()
        sample = ygpairs.get_pairs(self.ip, self.thread)
        while len(sample) > 0:
            if self.wait is not None: time.sleep(self.wait)
            if len(sample) > 0:
                self.compare_ids(sample)

                if maxcount is not None:
                    maxcount -= len(sample)
                    if maxcount <= 0: break

            sample = ygpairs.get_pairs(self.ip, self.thread)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="grab pairs of tweet ids from the pairs table and build similarity"
    )
    parser.add_argument('--ip',required=True,help='ip (or localhost) for this node')
    parser.add_argument('--thread',required=True,type=int,help="thread number for this node")
    parser.add_argument('--epsilon',type=float,help="minimum similarity value for saving a pair")
    parser.add_argument('--wait',type=float,help="wait time between samples")
    parser.add_argument('--clean',action='store_true',help="delete data in similarity table")
    parser.add_argument('--verbose',action='store_true',help="show lots of debug info")
    args = parser.parse_args()

    yglog.verbose = args.verbose

    with ygsim(ip=args.ip, thread=args.thread, wait=args.wait, epsilon=args.epsilon) as sim:
        sim.scan_pairs(clean=args.clean)

