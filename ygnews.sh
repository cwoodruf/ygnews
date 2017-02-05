#!/bin/bash

# how we identify ourselves to the db when polling for work
YGIP=localhost
YGTHREAD=1

# parameters needed for dbscan - arrived at by observation
YGEPSILON=0.28
YGMINCLUSTER=3

echo STARTING $YGIP $YGTHREAD `/bin/date`
if [ -d $HOME/ygnews ]
then
    cd $HOME/ygnews
elif [ -d $HOME/Desktop/ygnews ]
then
    cd $HOME/Desktop/ygnews
fi

# grabs news from the news feeds
time ./ygnews.py --ip=$YGIP --thread=$YGTHREAD

# extracts some useful features from the news stories
time ./ygfeatures.py 

# generates pairs of tweets that can be evaluated for relatedness
time ./ygpairs.py 

# calculates similarity between pairs of tweets and saves any non-zero results
# as this is the most time consuming part of processing it is possible to farm 
# this task out to multiple nodes by running multiple instances of the script
time ./ygsim.py --ip=$YGIP --thread=$(($YGTHREAD+1)) --epsilon=$YGEPSILON

# uses similarity results from ygsim to generate clusters using DBSCAN saving results to a file
time ./ygcluster.py --epsilon=$YGEPSILON --minsz=$YGMINCLUSTER --daysback=1 --interesting=0.9 > ./ygnews-`/bin/date +%Y%m%d_%H%M%S`.txt

echo FINISHED $YGIP $YGTHREAD `/bin/date`

