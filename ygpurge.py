#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
remove old data from various tables
should be run daily to ensure the db runs optimally
"""
import ygdb

conn = ygdb.conn()
cleanup = conn.cursor()
cleanup.execute("select id from features where created_at < now() - interval 7 day")

for row in cleanup:
    tweetid = row[0]
    print "deleting", tweetid, "data"
    remove = conn.cursor()
    remove.execute("delete from tweets where id = %s",(tweetid,))
    remove.execute("delete from tweetbigrams where id = %s",(tweetid,))
    remove.execute("delete from tweetwords where id = %s",(tweetid,))
    remove.execute("delete from features where id = %s",(tweetid,))
    remove.execute("delete from pairs where id1 = %s",(tweetid,))
    remove.execute("delete from pairs where id2 = %s",(tweetid,))
    remove.execute("delete from similarity where id1 = %s",(tweetid,))
    remove.execute("delete from similarity where id2 = %s",(tweetid,))
    remove.close()
    conn.commit()
cleanup.close()
conn.close()
print "done"

