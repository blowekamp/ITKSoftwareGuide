#!/usr/bin/env python
import sys
import os
import re
import shlex
import subprocess
import errno

#
# Tag defs
#
beginCmdLineArgstag = "BeginCommandLineArgs"
endCmdLineArgstag = "EndCommandLineArgs"
# beginCmdLineArgstag = "BeginCommandLineArgsTest"
# endCmdLineArgstag   = "EndCommandLineArgsTest"
fileinputstag = "INPUTS:"
fileoutputstag = "OUTPUTS:"
normalizedoutputstag = "NORMALIZE_EPS_OUTPUT_OF:"


def mkdir_p(path):
    """ Safely make a new directory, checking if it already exists"""
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def GetFilesInThisLine(line, tag):
    line.replace(fileoutputstag, "")  # Strip the tag away
    # squish more than one space into one
    line.replace("  ", " ").rstrip().lstrip()  # strip leading and trailing spaces
    outputfilesInThisLine = line.split(' ')
    return outputfilesInThisLine


def GetOutputFilesInThisLine(line):
    return GetFilesInThisLine(line, fileoutputstag)


def GetInputFilesInThisLine(line):
    return GetFilesInThisLine(line, fileinputstag)


def GetNormalizedFilesInThisLine(line):
    return GetFilesInThisLine(line, normalizedoutputstag)

## This class is initialized with a the starting line of
## the command processing, and the block of text for
## this command invocation


class OneCodeBlock():
    def __init__(self, sourceFile, id, codeblock, pathFinder):
        self.sourceFile = sourceFile
        self.id = id
        self.codeblock = codeblock
        self.inputs = []
        self.outputs = []
        self.MakeAllFileLists()
        self.pathFinder = pathFinder
        progBaseName = os.path.basename(self.sourceFile)[:-4]
        self.progFullPath = pathFinder.GetProgramPath(progBaseName)
        if not os.path.exists(self.progFullPath):
            print("ERROR:  Required program {0} does not exists.  Please rebuild ITK".format(self.progBaseName))
            sys.exit(-1)

    def DoInputsExists(self):
        for i in self.inputs:
            if i[0] != '/':  # if not a full path designation
                i = pathFinder.GetInputPath(i)
            if i == None:
                continue
            if not os.path.exists(i):
                return False
        return True

    def AreOutputsNewer(self):
        oldest_output = 100000000000000000000000
        print("Self Outputs {0}".format(self.outputs))
        print("Self Inputs {0}".format(self.inputs))
        for o in self.outputs:
            print("CHECKING TIME FOR: {0}".format(o))
            if os.path.exists(o):
                this_output_time = os.path.getmtime(o)
                print("This Ouptut Time: {0}".format(this_output_time))
                if this_output_time < oldest_output:
                    oldest_output = this_output_time
            else:
                print("Missing Output: {0}".format(o))
                return False
        newest_input = os.path.getmtime(self.progFullPath)
        for i in self.inputs:
            if i == None:
                continue
            print("CHECKING TIME FOR: {0}".format(i))
            if os.path.exists(i):
                this_input_time = os.path.getmtime(i)
                print("This Input Time: {0}".format(this_input_time))
                if this_input_time > newest_input:
                    newest_input = this_input_time
            else:
                print("Missing input {0}".format(i))
                sys.exit(-1)  # This should never happen because you should only run this function once all inputs exists.
        print("Newest Input: {0}, Oldest Output: {1}".format(newest_input, oldest_output))
        if newest_input < oldest_output:
            return True
        else:
            return False

    def GetCommandLine(self):
        commandLine = self.progFullPath + " "
        lineparse = re.compile(' *(.*): *(.*)')
        currLineNumber = self.id
        for currLine in self.codeblock:
            currLineNumber = currLineNumber + 1
            parseGroups = lineparse.search(currLine)
            if parseGroups == None:
                print("ERROR: Invalid parsing of {0} at line {1}".format(self.sourceFile, currLineNumber))
                sys.exit(-1)
            if parseGroups.group(1) == 'INPUTS':
                inputBaseFileName = parseGroups.group(2)
                inputFileName = pathFinder.GetInputPath(inputBaseFileName)
                if inputFileName == None:
                    print("ERROR: Invalid input {0} at {1} at line {2}".format(parseGroups.group(2),
                                                                               self.sourceFile, currLineNumber))
                    exit(-1)
                else:
                    commandLine = commandLine + " " + inputFileName
                    if not os.path.exists(inputFileName):
                        inputFileName = pathFinder.GetOutputPath(inputBaseFileName)
                    if not os.path.exists(inputFileName):
                        print("WARNING: Can not find {0} path, assuming it is autogenerated".format(inputFileName))
                    self.inputs.append(inputFileName)
            elif parseGroups.group(1) == 'OUTPUTS':
                outputFileName = pathFinder.GetOutputPath(parseGroups.group(2))
                commandLine = commandLine + " " + outputFileName
                self.outputs.append(outputFileName)
            elif parseGroups.group(1) == 'NORMALIZE_EPS_OUTPUT_OF':
                print('WARNING: WARNING: WARNING: NORMALIZE_EPS_OUTPUT_OF not yet implemented  ')
                pass  # HACK:  We need to figure out what to do with this, and when
            elif parseGroups.group(1) == 'ARGUMENTS':
                commandLine = commandLine + " " + parseGroups.group(2)
            elif parseGroups.group(1) == 'NOT_IMPLEMENTED':
                pass
        return commandLine

    def MakeAllFileLists(self):
        self.inputs = []
        self.outputs = []
        lineparse = re.compile(' *(.*): *(.*)')
        lineNumber = self.id
        for currLine in self.codeblock:
            lineNumber = lineNumber + 1
            parseGroups = lineparse.search(currLine)
            parseKey = parseGroups.group(1).rstrip().lstrip()
            if parseKey == '':
                continue  # Empty lines are OK
            elif parseKey == 'INPUTS':
                inputFile = currLine.replace("INPUTS:", "").rstrip().lstrip()
                inputFile = pathFinder.GetInputPath(inputFile)
                self.inputs.append(inputFile)
            elif parseKey == 'OUTPUTS':
                outputFile = currLine.replace("OUTPUTS:", "").rstrip().lstrip()
                outputFile = pathFinder.GetOutputPath(outputFile)
                self.outputs.append(outputFile)
            elif parseKey == 'ARGUMENTS':
                pass
            elif parseKey == 'NORMALIZE_EPS_OUTPUT_OF':
                pass
            elif parseKey == 'NOT_IMPLEMENTED':
                pass
            else:
                print("ERROR:  INVALID LINE IDENTIFIER {0} at line {1} in {2}".format(parseGroups.group(1), lineNumber, self.sourceFile))

    def Print(self):
        blockline = self.id
        print("=" * 80)
        print(self.sourceFile)
        for blocktext in self.codeblock:
            blockline += 1
            print("{0}  : {1}".format(blockline, blocktext))
        print self.GetCommandLine()
        print("^" * 80)


def ParseOneFile(sourceFile, pathFinder):
        #
        # Read each line and Parse the input file
        #
        # Get the command line args from the source file
    sf = open(sourceFile, 'r')
    INFILE = sf.readlines()
    sf.close()
    parseLine = 0
    starttagline = 0
    thisFileCommandBlocks = []
    for thisline in INFILE:
        parseLine += 1

        thisline = thisline.replace('//', '')
        thisline = thisline.replace('{', '').replace('}', '')
        thisline = thisline.rstrip().rstrip('/').rstrip().lstrip().lstrip('/').lstrip()
        # If the "BeginCommandLineArgs" tag is found, set the "starttagline" var and
        # initialize a few variables and arrays.
        if thisline.count(beginCmdLineArgstag) == 1:  # start of codeBlock
            starttagline = parseLine
            codeBlock = []
        elif thisline.count(endCmdLineArgstag) == 1:  # end of codeBlock
            ocb = OneCodeBlock(sourceFile, starttagline, codeBlock, pathFinder)
            thisFileCommandBlocks.append(ocb)
            starttagline = 0
        elif starttagline > 0:  # Inside a codeBlock
            codeBlock.append(thisline)
        else:  # non-codeBlock line
            pass
    return thisFileCommandBlocks

import os
import os.path
import stat
import time
from datetime import date, timedelta

dirsNotUsed = []


def datecheck(root, age):
    basedate = date.today() - timedelta(days=age)
    used = os.stat(root).st_mtime  # st_mtime=modified, st_atime=accessed
    year, day, month = time.localtime(used)[:3]
    lastused = date(year, day, month)
    return basedate, lastused


def getdirs(basedir, age):
    for root, dirs, files in os.walk(basedir):
        basedate, lastused = datecheck(root, age)
        if lastused < basedate:  # Gets files older than (age) days
            dirsNotUsed.append(root)


class ITKPathFinder:
    def __init__(self, itkSourceDir, itkBinaryDir, SWGuidBaseOutput):
        self.execDir = itkBinaryDir + '/bin'
        self.execDir = self.execDir.rstrip('/')
        self.outPicDir = SWGuidBaseOutput + '/Art/Generated'
        # Check if there are any input files that need to be flipped.
        self.outPicDir = os.path.realpath(self.outPicDir)
        self.outPicDir = self.outPicDir.rstrip('/')
        mkdir_p(self.outPicDir)

        # HACK:  Need beter search criteria
        searchPaths = '{0}/ExternalData/Testing/Data/Input:{0}/ExternalData/Brain:{1}/Testing/Data/Input/:{1}/Testing/Data/Baseline/Review:{1}/Testing/Data/Baseline/Iterators:{1}/Testing/Data/Baseline/IO:{1}/Testing/Data/Baseline/Filtering:{1}/Testing/Data/Baseline/BasicFilters:{1}/Testing/Data/Baseline/Algorithms:{1}/Examples/Data:{0}/Testing/Temporary:{0}/Modules/Nonunit/Review/test:{0}/ExternalData/Modules/Segmentation/LevelSetsv4/test/Baseline:{0}/ExternalData/Modules/IO/GE/test/Baseline:{0}/ExternalData/Examples/Filtering/test/Baseline:{0}/ExternalData/Examples/Data/BrainWeb:{0}/Examples/Segmentation/test:{2}/Art/Generated:{0}ExternalData/Testing/Data/Input'.format(itkBinaryDir, itkSourceDir, SWGuidBaseOutput)
        dirtyDirPaths = searchPaths.split(':')

        self.searchDirList = []
        for eachpath in dirtyDirPaths:
            if os.path.isdir(eachpath):
                self.searchDirList.append(os.path.realpath(eachpath))

        print self.searchDirList

    def GetProgramPath(self, execfilenamebase):
        testPath = self.execDir + '/' + execfilenamebase
        if os.path.exists(testPath):
            return testPath
        else:
            print("ERROR:  {0} does not exists".format(testPath))
            sys.exit(-1)

    def GetInputPath(self, inputBaseName):
        for checkPath in self.searchDirList:
            testPath = checkPath + '/' + inputBaseName
            if os.path.exists(testPath):
                return testPath
            else:
                pass
                # print('##Warning: Missing input {0}'.format(testPath))
        return inputBaseName

    def GetOutputPath(self, outputBaseName):
        outPath = self.outPicDir + '/' + outputBaseName
        # outPath = outPath.replace(self.outPicDir+'/'+self.outPicDir, self.outPicDir ) #Avoid multiple path concatenations
        # if not os.path.exists(outPath):
            # print("@@Warning: Output missing {0}".format(outPath))
        return outPath

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Parse an ITK source tree and run programs in order to make output files for Software Guide.')
    parser.add_argument('--itkSourceDir', dest='itkSourceDir', action='store', default=None,
                        help='The path to the ITK source tree.')
    parser.add_argument('--itkExecDir', dest='itkExecDir', action='store', default=None,
                        help='The path to the ITK binary tree bin directory were executables are found.')
    parser.add_argument('--SWGuidBaseOutput', dest='SWGuidBaseOutput', action='store', default=None,
                        help="The base directory of the output directory.")

    args = parser.parse_args()

    itkBinaryDir = os.path.dirname(args.itkExecDir)
    pathFinder = ITKPathFinder(args.itkSourceDir, itkBinaryDir, args.SWGuidBaseOutput)

    allCommandBlocks = []
    for rootDir, dirList, fileList in os.walk(args.itkSourceDir):
        if rootDir.count('ThirdParty') >= 1:
            # print("Passing on: {0}".format(rootDir))
            continue

        for currFile in fileList:
            if currFile[-4:] != ".cxx":  # Only parse cxx files
                    # print("NOT PARSING: {0} because it has wrong extension {1}".format(currFile,currFile[-r:]))
                continue
            sourceFile = os.path.realpath(rootDir + '/' + currFile)

            ## A dictionary indexed by starting line to the command blocks
            allCommandBlocks += ParseOneFile(sourceFile, pathFinder)

    max_depth = 6
    for depth in range(0, max_depth):  # Only look 4 items deep, then assume failures occured
        if len(allCommandBlocks) == 0:
            print("ALL WORK COMPLETED!")
            break
        if depth == max_depth - 1:
            print("FAILED TO COMPLETE ALL PROCESSING.")
            sys.exit(-1)
        remainingCommandBlocks = []
        print("Running depth level {0} with {1} codeblocks".format(depth, len(allCommandBlocks)))
        for blockstart in allCommandBlocks:
            if blockstart.DoInputsExists() == False:
                blockstart.AreOutputsNewer()
                print(' ' * 80 + "\nJob Not Yet Ready To Run")
                print(blockstart.inputs)
                print('*' * 80)
                remainingCommandBlocks.append(blockstart)
                runCommand = blockstart.GetCommandLine()
                # print(runCommand)
                # print('*'*80)
                continue
            else:
                completedAlready = blockstart.AreOutputsNewer()
                if completedAlready == True:
                    print(' ' * 80 + "\nJob Already Done")
                    # runCommand = blockstart.GetCommandLine()
                # print(runCommand)
                    print('-' * 80)
                elif completedAlready == False:
                    print(' ' * 80 + "\nNeed to run")
                    pass
                    blockstart.Print()
                    runCommand = blockstart.GetCommandLine()
                    try:
                        retcode = subprocess.call(runCommand, shell=True)
                        if retcode < 0:
                            print >>sys.stderr, "Child was terminated by signal", -retcode
                        else:
                            print >>sys.stderr, "Child returned", retcode
                    except OSError, e:
                        print >>sys.stderr, "Execution failed:", e
                    runCommand = blockstart.GetCommandLine()
                    print(runCommand)
                    print('+' * 80 + "\nNeed to run")
                else:
                    print("ERROR:  Invalid status given.")
                    sys.exit(-1)
        allCommandBlocks = remainingCommandBlocks


print('$^&!' * 20)
