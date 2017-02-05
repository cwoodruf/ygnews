"""
author: Cal Woodruff, cwoodruf@sfu.ca
basic mixin class to standardize db access
"""
import ygdb

class ygcursors(object):

    def __init__(self):
        self.conn = None

    def opendb(self):
        self.closedb()
        self.conn = ygdb.conn()

    def closedb(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def getcursor(self):
        if self.conn is None:
            self.opendb()
        return self.conn.cursor()

    def _commit(self):
        if self.conn is None: return
        self.conn.commit()

    # allows for the use of the "with" keyword
    def __enter__(self):
        return self

    # ensure we close db handle when leaving "with" block
    def __exit__(self, xc_type, exc_value, traceback):
        self.closedb()

