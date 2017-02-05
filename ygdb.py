"""
author: Cal Woodruff, cwoodruf@sfu.ca
connect to mysql db ygnews
"""
from ygsecrets import ygnewsdb
import MySQLdb
connection = None

def conn(db=ygnewsdb):
    global connection
    connection = MySQLdb.connect(
        host=db['host'], 
        port=db['port'], 
        db=db['db'], 
        user=db['user'], 
        passwd=db['pw']
    )
    return connection

if __name__ == '__main__':
    c = conn()
    print c
    c.close()
