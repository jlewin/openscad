import os
import StringIO
import sys

import xmltodict
import json

# Open the tag file and extract the directory name containing the test.xml file
TAGfile = open(sys.argv[1]+"/Testing/TAG", 'r')
dirname = TAGfile.readline().strip()
resultsFile = sys.argv[1]+"/Testing/"+dirname+"/Test.xml"

xl = file(resultsFile) 
result = xmltodict.parse(xl)
#print json.dumps (result) 

tests = []

# Iterate test results
for t in result["Site"]["Testing"]["Test"]:
    mx = {}
    for m in t["Results"]["NamedMeasurement"]:
        mx[m["@name"]] = m["Value"]

    tests.append( {
        "status": t["@Status"],
        "name": t["Name"],
        "elapsed": mx["Execution Time"],
        "completed": mx["Completion Status"] } ) 

with open(sys.argv[2], 'w') as outfile:
    json.dump(tests, outfile, indent=4, separators=(',', ': '))

print "Dumping results to : " + os.path.abspath(sys.argv[2])

#print json.dumps(tests, sort_keys=True, indent=4, separators=(',', ': '))


