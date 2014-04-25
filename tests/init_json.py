#!/usr/bin/python

import string
import sys
import re
import os
import hashlib
import subprocess
import time
import platform
import json

def main():
    print "**************** Init *******************"

    # Remove any existing file
    try:
        os.remove("results.jso_")
    except OSError:
        pass

    # Prepend opening array bracket and copy contents
    with open("results.jso_", 'w') as jsonfile:
        jsonfile.write("[")

if __name__=='__main__':
    main()
