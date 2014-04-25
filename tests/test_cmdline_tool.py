#
# Regression test driver for cmd-line tools
#
# Usage: test_cmdline_tool.py [<options>] <tool> <arguments>
#
# If the -g option is given or the TEST_GENERATE environment variable is set to 1,
# *-expected.<suffix> files will be generated instead of running the tests.
# 
# Any generated output is written to the file `basename <argument`-actual.<suffix>
# Any warning or errors are written to stderr.
#
# Returns 0 on passed test
#         1 on error
#         2 on invalid cmd-line options
# 
# Author: Marius Kintel <marius@kintel.net>
#

import sys
import os
import glob
import subprocess
import re
import getopt
import shutil
import platform
import string
import json
import time

def initialize_environment():
    if not options.generate: options.generate = bool(os.getenv("TEST_GENERATE"))
    return True

def init_expected_filename():
    global expecteddir, expectedfilename

    expected_testname = options.testname

    if hasattr(options, "expecteddir"):
        expected_dirname = options.expecteddir
    else:
        expected_dirname = expected_testname

    # the expected filename is semi-convention driven but allows for override via options['expecteddir']

    # otherwise the convention is [regressiondir]/[expected_dirname]/[filename]-expected.[suffix]

    expecteddir = os.path.join(options.regressiondir, expected_dirname)
    expectedfilename = os.path.join(expecteddir, options.filename + "-expected." + options.suffix)
    expectedfilename = os.path.normpath(expectedfilename)

def init_actual_filename():
    global actualdir, actualfilename

    cmdname = os.path.split(options.cmd)[1]
    actualdir = os.path.join(os.getcwd(), options.testname + "-output")
    actualfilename = os.path.join(actualdir, options.filename + "-actual." + options.suffix)
    actualfilename = os.path.normpath(actualfilename)

def verify_test(testname, cmd):
    global expectedfilename
    if not options.generate:
        if not os.path.isfile(expectedfilename):
            print >> sys.stderr, "Error: test '%s' is missing expected output in %s" % (testname, expectedfilename)
            return False
    return True

def execute_and_redirect(cmd, params, outfile):
    retval = -1
    try:
        proc = subprocess.Popen([cmd] + params, stdout=outfile, stderr=subprocess.STDOUT)
        out = proc.communicate()[0]
        retval = proc.wait()
    except:
        print >> sys.stderr, "Error running subprocess: ", sys.exc_info()[1]
        print >> sys.stderr, " cmd:", cmd
        print >> sys.stderr, " params:", params
        print >> sys.stderr, " outfile:", outfile
    if outfile == subprocess.PIPE: return (retval, out)
    else: return retval

def get_normalized_text(filename):
    try: 
        f = open(filename)
        text = f.read()
    except: 
        text = ''
    return text.strip("\r\n").replace("\r\n", "\n") + "\n"

def compare_text(expected, actual):
    return get_normalized_text(expected) == get_normalized_text(actual)

def compare_default(resultfilename, info):
    print >> sys.stderr, 'diff text compare: '
    print >> sys.stderr, ' expected textfile: ', expectedfilename
    print >> sys.stderr, ' actual textfile: ', resultfilename


    r = {'expected': expectedfilename, 'actual': resultfilename}

    info['compare'] = { 'comparison': r, 'type':'diff' }

    if not compare_text(expectedfilename, resultfilename):
        r['matches'] = False
        if resultfilename:
            execute_and_redirect("diff", [expectedfilename, resultfilename], sys.stderr)
        return False
    r['matches'] = True
    return True

def compare_png(resultfilename, info):
    compare_method = 'pixel'
    #args = [expectedfilename, resultfilename, "-alpha", "Off", "-compose", "difference", "-composite", "-threshold", "10%", "-blur", "2", "-threshold", "30%", "-format", "%[fx:w*h*mean]", "info:"]
    args = [expectedfilename, resultfilename, "-alpha", "Off", "-compose", "difference", "-composite", "-threshold", "10%", "-morphology", "Erode", "Square", "-format", "%[fx:w*h*mean]", "info:"]

    # for systems with older imagemagick that doesnt support '-morphology'
    # http://www.imagemagick.org/Usage/morphology/#alturnative
    if options.comparator == 'old':
      args = [expectedfilename, resultfilename, "-alpha", "Off", "-compose", "difference", "-composite", "-threshold", "10%", "-gaussian-blur","3x65535", "-threshold", "99.99%", "-format", "%[fx:w*h*mean]", "info:"]

    if options.comparator == 'ncc':
      # for systems where imagemagick crashes when using the above comparators
      args = [expectedfilename, resultfilename, "-alpha", "Off", "-compose", "difference", "-metric", "NCC", "tmp.png"]
      options.convert_exec = 'compare'
      compare_method = 'NCC'

    msg = 'ImageMagick image comparison: '  + options.convert_exec + ' '+ ' '.join(args[2:])
    msg += '\n expected image: ' + expectedfilename + '\n'
    print >> sys.stderr, msg

    r = { 'type': 'png' }

    info['compare'] = r

    if not resultfilename:
        err_msg = "Error: Error during test image generation"
        r['error'] = err_msg
        print >> sys.stderr, err_msg
        return False
    print >> sys.stderr, ' actual image: ', resultfilename

    # Execute the comparision
    (retval, output) = execute_and_redirect(options.convert_exec, args, subprocess.PIPE)
    print "Imagemagick return", retval, "output:", output
    r['executed'] = {
            'retval' : retval, 
            'options': options.convert_exec + ' ' + ' '.join(args[2:]),
            'expected': expectedfilename,
            'actual': resultfilename,
            'output': output.strip() }

    match = False; error_msg = ''; err = ''

    if retval == 0:
        if compare_method=='pixel':
            err = int(float(output.strip()))
            match = err < 32

            if not match: 
                print >> sys.stderr, err, ' pixel errors'
                error_msg = str(err) + ' pixel errors'

        elif compare_method=='NCC':
            thresh = 0.95; err = float(output.strip())
            match = err > thresh or err==0.0

            if not match:
                print >> sys.stderr, err, ' Images differ: NCC comparison < ', thresh
                error_msg = str(err) + ' Images differ: NCC comparison < ' + str(thresh)
    
    r['comparison'] = { 
        'err': err, 
        'matches': match, 
        'method': compare_method, 
        'comparator': options.comparator,
        'error_msg': error_msg}

    return match

def compare_with_expected(resultfilename, info):
    
    if not options.generate:
        if "compare_" + options.suffix in globals(): return globals()["compare_" + options.suffix](resultfilename, info)
        else: return compare_default(resultfilename, info)
    return True

def run_test(testname, cmd, args, info):
    cmdname = os.path.split(options.cmd)[1]

    if options.generate: 
        if not os.path.exists(expecteddir): os.makedirs(expecteddir)
        outputname = expectedfilename
    else:
        if not os.path.exists(actualdir): os.makedirs(actualdir)
        outputname = actualfilename
    outputname = os.path.normpath(outputname)

    outfile = open(outputname, "wb")

    try:
        cmdline = [cmd] + args + [outputname]
        print cmdline

        # actualfilename is the output/results file

        start = time.time();
        proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        results = proc.communicate()
        errtext = results[1]
        text = results[0]

        deprecated = False
        hasError = False

        if errtext != None and len(errtext) > 0:
            print >> sys.stderr, "Error output: " + errtext
            deprecated = "DEPRECATED" in errtext
            hasError = True

        outfile.close()
        
        info['subject'] = {
            'exetime': time.time() - start,    # actual execution duration
            'stderr': errtext,
            'stdout': text,
            'errorDetected': hasError,
            'deprecated': deprecated,
            'cmdline': cmdline  }

        if proc.returncode != 0:
            print >> sys.stderr, "Error: %s failed with return code %d" % (cmdname, proc.returncode)
            return None

        return outputname
    except OSError, err:
        print >> sys.stderr, "Error: %s \"%s\"" % (err.strerror, cmd)
        return None

class Options:
    def __init__(self):
        self.__dict__['options'] = {}
        
    def __setattr__(self, name, value):
        self.options[name] = value
    def __getattr__(self, name):
        return self.options[name]

def usage():
    print >> sys.stderr, "Usage: " + sys.argv[0] + " [<options>] <cmdline-tool> <argument>"
    print >> sys.stderr, "Options:"
    print >> sys.stderr, "  -g, --generate           Generate expected output for the given tests"
    print >> sys.stderr, "  -s, --suffix=<suffix>    Write -expected and -actual files with the given suffix instead of .txt"
    print >> sys.stderr, "  -e, --expected-dir=<dir> Use -expected files from the given dir (to share files between test drivers)"
    print >> sys.stderr, "  -t, --test=<name>        Specify test name instead of deducting it from the argument (defaults to basename <exe>)"
    print >> sys.stderr, "  -f, --file=<name>        Specify test file instead of deducting it from the argument (default to basename <first arg>)"
    print >> sys.stderr, "  -c, --convexec=<name>    Path to ImageMagick 'convert' executable"

if __name__ == '__main__':
    # Handle command-line arguments
    try:
        opts, args = getopt.getopt(sys.argv[1:], "gs:e:c:t:f:m", ["generate", "convexec=", "suffix=", "expected_dir=", "test=", "file=", "comparator="])
    except getopt.GetoptError, err:
        usage()
        sys.exit(2)

    global options
    options = Options()
    options.regressiondir = os.path.join(os.path.split(sys.argv[0])[0], "regression")
    options.generate = False
    options.suffix = "txt"
    options.comparator = ""

    for o, a in opts:
        if o in ("-g", "--generate"): options.generate = True
        elif o in ("-s", "--suffix"):
            if a[0] == '.': options.suffix = a[1:]
            else: options.suffix = a
        elif o in ("-e", "--expected-dir"):
            options.expecteddir = a
        elif o in ("-t", "--test"):
            options.testname = a
        elif o in ("-f", "--file"):
            options.filename = a
        elif o in ("-c", "--convexec"): 
            options.convert_exec = os.path.normpath( a )
        elif o in ("-m", "--comparator"):
            options.comparator = a

    # <cmdline-tool> and <argument>
    if len(args) < 2:
        usage()
        sys.exit(2)
    options.cmd = args[0]

    # If only one test file, we can usually deduct the test name from the file
    if len(args) == 2:
        basename = os.path.splitext(args[1])[0]
        path, options.filename = os.path.split(basename)
        print >> sys.stderr, basename
        print >> sys.stderr, path, options.filename

    print >> sys.stderr, options.filename
    if not hasattr(options, "filename"):
        print >> sys.stderr, "Filename cannot be deduced from arguments. Specify test filename using the -f option"
        sys.exit(2)

    if not hasattr(options, "testname"):
        options.testname = os.path.split(args[0])[1]

    # Initialize and verify run-time environment
    if not initialize_environment(): sys.exit(1)

    init_expected_filename()
    init_actual_filename()

    # Verify test environment
    verification = verify_test(options.testname, options.cmd)
    testdata = {'options': options.options, 'name': options.testname + '_' + options.filename}

    resultfile = run_test(options.testname, options.cmd, args[1:], testdata)
    if not resultfile: exit(1)

    invalid = False

    if not verification or not compare_with_expected(resultfile, testdata): 
        invalid = True

with open("results.jso_", "a") as outfile:
    json.dump(testdata, outfile, separators=(',', ': '))
    outfile.write(",\n")

if invalid:
    exit(1)


