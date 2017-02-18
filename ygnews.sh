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

if [ -f ygsim.pid ]
then
    echo ygsim still running
else
    (echo $$ > ygsim.pid;
    # generates pairs of tweets that can be evaluated for relatedness
    time ./ygpairs.py 

    # calculates similarity between pairs of tweets and saves any non-zero results
    # as this is the most time consuming part of processing it is possible to farm 
    # this task out to multiple nodes by running multiple instances of the script
    # however, in practice there are deadlock problems with the db - at least on my 
    # crappy system
    time ./ygsim.py --ip=$YGIP --thread=$YGTHREAD --epsilon=$YGEPSILON;
    /bin/rm ygsim.pid) &
fi

# uses similarity results from ygsim to generate clusters using DBSCAN saving results to a file
time ./ygcluster.py --epsilon=$YGEPSILON --minsz=$YGMINCLUSTER --daysback=1 --interesting=0.0 > ./archives/ygnews-`/bin/date +%Y%m%d_%H%M%S`.txt
time ./ygcluster.py --epsilon=$YGEPSILON --minsz=$YGMINCLUSTER --daysback=1 --tweets > ./archives/ygnews-tweets-`/bin/date +%Y%m%d_%H%M%S`.txt

echo FINISHED $YGIP $YGTHREAD `/bin/date`

