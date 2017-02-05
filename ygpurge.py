#!/usr/bin/env python
"""
author: Cal Woodruff, cwoodruf@sfu.ca
remove old data from various tables
should be run daily to ensure the db runs optimally
"""
import ygdb
import time

start = time.time()
conn = ygdb.conn()
cleanup = conn.cursor()
print "purging features"
cleanup.execute("delete from features where created_at < now() - interval 2 day")
conn.commit()
elapsed = time.time() - start
print "purging tweets",elapsed,"s"
cleanup.execute("delete from tweets where id not in (select id from features)")
conn.commit()
elapsed = time.time() - start
print "purging tweetwords",elapsed,"s"
cleanup.execute("delete from tweetwords where id not in (select id from features)")
conn.commit()
elapsed = time.time() - start
print "purging links",elapsed,"s"
cleanup.execute("delete from links where id not in (select id from features)")
conn.commit()
elapsed = time.time() - start
print "purging tweetbigrams",elapsed,"s"
cleanup.execute("delete from tweetbigrams where id not in (select id from features)")
conn.commit()
elapsed = time.time() - start
print "purging similarity",elapsed,"s"
cleanup.execute("delete from similarity where id1 not in (select id from features)")
cleanup.execute("delete from similarity where id2 not in (select id from features)")
conn.commit()
elapsed = time.time() - start
print "purging pairs",elapsed,"s"
# deleting stuff from the pairs table doesn't seem to be happening as expected ...
# this takes a lot longer but is guaranteed to produce just what we want
# we assume that ygpairs.py has been run first
try:
    cleanup.execute("drop table pairs_new")
except:
    pass
cleanup.execute("create table pairs_new (like pairs_template)")
cleanup.execute(
    "insert into pairs_new "
    "select * from pairs "
    "where id1 in (select id from features where selected is not null) "
    "and id2 in (select id from features where selected is not null) "
    "and ip is not null"
)
cleanup.execute("alter table pairs rename to pairs_deleted")
cleanup.execute("alter table pairs_new rename to pairs")
cleanup.execute("drop table pairs_deleted")
conn.commit()
elapsed = time.time() - start
print "finished",elapsed
cleanup.close()
conn.close()
print "done"

