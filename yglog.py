"""
author: Cal Woodruff, cwoodruf@sfu.ca
logs messages to screen if "verbose" is true
normally verbose would be false
"""
verbose = True

def vprint(*args):
    if verbose: print(" ".join(map(str,args)))


