# ygnews
Twitter news feed clustering service


Date: 2017-01-15
Author: Cal Woodruff cwoodruf@sfu.ca, cwoodruf@gmail.com, 778 232 5078

The software in this directory is an implementation of a service for gathering
news tweets, clustering them and saving tweets representing newsworthy clusters.
See the NLPtesttaskTwitterpush.pdf file for a description of the project 
requirements.

To run the service:

- create the mysql database using the ygnews-schema.mysql file
- fill in the twitter and mysql credentials in a ygsecrets.py file
  an example is provided 
- initially run the ygnews.sh script to initialize the data
- update your crontab to include commands like those in ygnews.cron
  this will run the service every 10 minutes

System:

The system was developed with Python 2.7 and Mysql 5.5 on a Ubuntu 14.04 system.

Software:

ygnews.sh - main script that runs the service - outputs ygnews.txt with interesting tweets

ygnews.py - polls for tweets from twitter
ygimport.py - library used by ygnews.py to update the db
              can also be run as a stand alone script
ygfeatures.py - extract useful features from tweets 
ygpairs.py - creates lists of pairs to tweets to process
ygsim.py - can be run on multiple servers, processes tweet pairs
           saves similarity data to similarity
ygcluster.py - generates clusters and can be used to find interesting clusters
ygpurge.py - utility script to remove old data from the database

ygcursors.py - base class used for db connectivity by other classes
ygdb.py - basic database connection
yglog.py - very basic console logging that checks for verbosity
ygsecrets.py - credentials file

Database tables:

feeds - list of feeds and ip/thread ids of "owners" of those feeds
        use the ip/thread to farm out work to different processes if necessary 
        see ygnews.sh for how ip and thread are invoked

features - features used to analyze tweets when calculating pair-wise similarity
links - links including retweet and quote links for tweets
user_features - view combining users with features
users - feed metadata

pairs - simply ordered pairs of tweets that can be analyzed for similarity
pairs_template - template table for making the pairs table
similarity - for a given ordered pair of tweet ids stores the similarity 
similarity_template - template table for making the similarity table

stopwords - common words that are ignored when processing tweets
tweets - raw tweet json from twitter
tweetwords - word frequencies by tweet id

tweetbigrams - bigrams by tweet id (not currently used)
words - word frequencies (not currently used)
bigrams - bigram frequencies (not currently used)

Clustering:

The main purpose of the system is to create meaningful groups of tweets.
The difficulty is that it is not known beforehand how many clusters of tweets
"make sense" for the gathered data. The DBSCAN algorithm is an example of 
an algorithm which does not require a-priori knowledge of the number of
clusters.

The DBSCAN cluster algorithm is implemented in ygcluster.py. This algorithm
requires two parameters (epsilon and minsz) to be set by the end user. 
Epsilon is the minimum similarity for two tweets to be considered related. minsz
is the smallest allowable number of tweets in a cluster. In ygnews.sh these
are set to values that appear to work relatively well with the data sources
being queried. However, with different input data the parameters may no
longer be optimal. In particular, the epsilon value is likely
to be sensitive to input data.

Cluster algorithms require similarity or distance calculations to determine
which items belong together. In this case what appears to work is the number
of links shared by a pair of tweets and the jaccard distance of complete set 
of words in the pair of tweets. Other measures such as jaccard with bag of words
or bag of bigrams, tf.idf cosine similarity were found to either be too time
consuming to be practical or not good measures of similarity.

Parallelization:

Some of the tasks run by the service can be time consuming on a
large data set. In recognition of this, some scripts are designed to
be run on multiple servers. In particular the ygnews.py and ygsim.py
scripts can be set up to run on multiple servers or run as multiple
instances on a single server. None of the software uses threading
mainly to avoid concurrency issues. The goal is to be stable and reliable
and to run in a predictable amount of time. When "cold start" tested the
ygnews.sh script finished in about 1 minute.

TODO:

- unit and functional tests
- port db to postgres - InnoDB was extremely slow for some operations
- create stored procedures for some common actions 
  (e.g. the summarize function in ygfeatures.py or the calls in ygpurge.py)


