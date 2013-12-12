#!/usr/bin/env python2.7
# 
# Copyright (C) 2013  Travis Brown (travisb@travisbrown.ca)
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import unittest
import argparse
import sys
import os
import subprocess
import time
import fcntl
import errno
import select
import re
import collections
import pprint

# A hack to allow us to pass the debug setting from lousy as a script to lousy as a library
try:
	_debug = unittest._lousy_debug
except:
	pass

class FrameBufferCell(object):
	'''Class which tracks the value and attributes of a character cell in the
	   framebuffer.
	'''
	char = ''
	attributes = 0

	# Various bit-flag attributes
	fl_set = (1 << 0) # This cell has a valid value

	def __init__(self):
		pass

class DumbTerminal(object):
	'''Base class for all the emulated terminals'''

	framebuffer = None

	rows = 24
	cols = 80
	current_row = 0
	current_col = 0
	tabstop = 8

	def __init__(self):
		self.rows = 24
		self.cols = 80
		self.current_row = 0
		self.current_col = 0

		self.framebuffer = [[FrameBufferCell() for col in range(self.cols)] for row in range(self.rows)]

	def dumpFrameBuffer(self):
		'''Print out the characters of the framebuffer as it stands. Note that this is
		   only an approximation as blank cells are written as spaces.
		'''
		sys.stdout.write('\n   ')
		for col in range(self.cols):
			if col % 10 == 0 and col > 0:
				sys.stdout.write('%s' % str((col / 10) % 10))
			else:
				sys.stdout.write(' ')

		sys.stdout.write('\n   ')
		for col in range(self.cols):
			sys.stdout.write('%s' % str(col % 10))

		sys.stdout.write('\n  +')
		for col in range(self.cols):
			sys.stdout.write('-')
		sys.stdout.write('+\n')

		for row in range(self.rows):
			if row % 10 == 0 and row != 0:
				sys.stdout.write('%s|' % str(row % 100))
			else:
				sys.stdout.write(' %s|' % str(row % 10))
			for col in range(self.cols):
				cell = self.cell(row, col)

				if cell.char == '':
					sys.stdout.write(' ')
				elif cell.char == '\t':
					sys.stdout.write(' ')
				else:
					sys.stdout.write(cell.char)
			sys.stdout.write('|\n')
		sys.stdout.write('  +')
		for col in range(self.cols):
			sys.stdout.write('-')
		sys.stdout.write('+\n')

	def cell(self, row, col):
		'''Retreive the FrameBufferCell for the given location. Returns None if the cell is out of range.
		'''
		if row < 0 or row >= self.rows:
			return None
		if col < 0 or col >= self.cols:
			return None

		return self.framebuffer[row][col]

	def interpret(self, c):
		'''Take the given character and interpret it'''
		cell = self.cell(self.current_row, self.current_col)

		if c == '\n':
			self.current_row += 1
		elif c == '\r':
			self.current_col = 0
		elif c == '\b':
			# Interpret the bell character, but don't do anything with it
			pass
		elif c == '\t':
			# Emulate fixed tab stops

			# If the tabstop would move beyond the edge of the
			# screen and overwrite the last character don't
			# write it.
			if self.current_col != self.cols - 1:
				cell.char = '\t'

			tabstop = int((self.current_col + self.tabstop)/self.tabstop) * self.tabstop
			if tabstop >= self.cols:
				tabstop = self.cols - 1

			self.current_col = tabstop
		else:
			cell.char = c
			self.current_col += 1

		if self.current_col == self.cols:
			self.current_col = 0
			self.current_row += 1

		if self.current_row == self.rows:
			del self.framebuffer[0]
			self.framebuffer.append([FrameBufferCell() for col in range(self.cols)])
			self.current_row -= 1

class VT100(DumbTerminal):
	'''VT100 terminal emulator'''

	def __init__(self):
		DumbTerminal.__init__(self)

class Vtty(object):
	'''Vtty is a terminal emulator which interprets the output of a process and keeps a
	   virtual framebuffer which can be examined to confirm process output.
	'''

	emulation = None

	def __init__(self, emulation='vt100'):
		'''emulation is the terminal emulator featureset and control codes to emulate.
		   Valid values are:
		   dumb
		   vt100
		'''
		if emulation is True:
			emulation = 'vt100'

		if emulation == 'dumb':
			self.emulation = DumbTerminal()
		elif emulation == 'vt100':
			self.emulation = VT100()
		else:
			raise ValueError('%s is not a supported terminal emulation type' % emulation)

	def append(self, input):
		'''Interpret the given stream of bytes to make their modification to the current
		   state of the virtual terminal.
		'''
		for c in input:
			emulation.interpret(c)

class ProcessPipe(object):
	'''File object to interact with processes.
	   Any output from the process will be output with a prefix and stored until
	   queried by the test.
	   '''

	prefix = ''
	closed = False
	buffer = ''
	mirror = None

	def __init__(self):
		self.pipes = os.pipe()
		self._setCloseExec(self.pipes[0])
		self._setCloseExec(self.pipes[1])

	def setPrefix(self, prefix):
		self.prefix = prefix

	def setMirror(self, newMirror):
		'''A mirror is an object which the ProcessPipe calls obj.append() on with the
		   newly read data. Useful for alternative interpretations of the output.
		'''
		self.mirror = newMirror

	def fileno(self):
		return self.pipes[self._direction]

	def _setCloseExec(self, fd):
		flags = fcntl.fcntl(fd, fcntl.F_GETFD)
		fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

	def _setNonBlocking(self, fd):
		flags = fcntl.fcntl(fd, fcntl.F_GETFL)
		fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

	def escapeAscii(self, string):
		'''Given an ascii string escape all non-printable characters to be printable'''

		# encoding doesn't work for \t \n and \r so we must do it ourselves
		def escape_whitespace(character):
			if character == '\t':
				return '\\t'
			else:
				return character

		string = ''.join(map(escape_whitespace, string))
		return string.encode('unicode_escape')

	def write(self, string):
		'''Returns number of bytes successfully written'''
		lines = self.escapeAscii(string).split('\n')
		for line in lines[:-1]:
			print '%s sent: "%s\\n"' % (self.prefix, line)
		if lines[-1] != '':
			print '%s sent: "%s"' % (self.prefix, lines[-1])
		return os.write(self.pipes[self._fileno], string)

	def read(self):
		'''Return a string of all the available output. An empty string is returned when no output is available'''

		# If we have data in our buffer then we shouldn't wait to read more data
		if len(self.buffer) > 0:
			timeout = 0.0
		else:
			timeout = 0.1

		ready, _, _ = select.select([self.pipes[self._fileno]], [], [], timeout)
		if len(ready) == 0:
			output = self.buffer
			self.buffer = ''
			return output

		output = os.read(self.pipes[self._fileno], 102400)

		if self.mirror is not None:
			self.mirror.append(output)

		if len(output) > 0:
			lines = self.escapeAscii(output).split('\\n')
			for line in lines[:-1]:
				print '%s received: "%s\\n"' % (self.prefix, line)
			if lines[-1] != '':
				print '%s received: "%s"' % (self.prefix, lines[-1])

		output = self.buffer + output
		self.buffer = ''

		return output

	def readLine(self, fullLineOnly=True):
		'''Return a string with the next available line of output from
		   the process. The trailing newline is trimmed.
		   None is returned when no line is available.
		   fullLineOnly=False will return a partial line if it is next in the queue.
		'''
		self.buffer = self.read()

		if '\n' in self.buffer:
			output, self.buffer = self.buffer.split('\n', 1)
			return output

		if not fullLineOnly and len(self.buffer) > 0:
			output = self.buffer
			self.buffer = ''
			return output

		return None

	def readSimple(self, fullLineOnly=True):
		'''Returns a string of all the available output in simplified
		form. An empty string is returned when no output is available.
		Returns a string with:
			- carriage returns removed.
			- Only full lines
		'''
		output = self.readLine(fullLineOnly=fullLineOnly)
		if output is None:
			return ''

		return output.translate(None, '\r')

class InProcessPipe(ProcessPipe):
	'''ProcessPipe which represents stdin'''
	_direction = 0
	_fileno = 1

class OutProcessPipe(ProcessPipe):
	'''ProcessPipe which respresnts stdout or stderr'''
	_direction = 1
	_fileno = 0

class PtyProcessPipe(ProcessPipe):
	'''ProcessPipe which uses a pty to connect to the child instead of regular pipes.
	   This is useful for interactive processes.
	'''

	_direction = 1
	_fileno = 0

	def __init__(self):
		self.pipes = os.openpty()
		self._setCloseExec(self.pipes[0])

class Process(object):
	'''Class for interacting with processes'''

	def __init__(self, command, shell=False, pty=False):
		'''command a list of the command and then arguments to run as the process
		   shell is True if the command should be run in the shell and False otherwise.
		   pty is whether to use a pty or a normal pipe to communicate with the process.
		   If pty is not false true there are two ways to access the output of the process.
		   Using the process.read*() methods will return a line based representation of what
		   the process output. Using the process.vty object (an instance of the Vtty class)
		   it is possible to see an interpretted view as a virtual terminal might show the
		   output.

		   Valid values for pty:
		     False - Don't start process in pty
		     True  - Start process in pty using default terminal emulation
		     vt100 - Start process in pty using vt100 emulation

		   If shell is True then the command list is converted into a space separate string
		   to be interpretted by the shell.
		'''

		if pty:
			self.stdin = PtyProcessPipe()
			self.stdout = self.stdin
			self.stderr = self.stdin
		else:
			self.stdin = InProcessPipe()
			self.stdout = OutProcessPipe()
			self.stderr = OutProcessPipe()

		self.returncode = None
		self.running = False

		if shell:
			cmd = ' '.join(command)
		else:
			cmd = command
		self.process = subprocess.Popen(cmd, shell=shell, stdin=self.stdin, stdout=self.stdout,
				                stderr=self.stderr)

		self.running = True

		prefix = '[ %s(%d) ]' % (command[0], self.process.pid)

		self.stdin.setPrefix(prefix)
		self.stdout.setPrefix(prefix)
		self.stderr.setPrefix(prefix)

	def terminate(self):
		'''Forcefully terminate the child process if it hasn't already terminated'''
		if self.running:
			self.process.kill()
			self.waitForTermination()
			self.returncode = self.process.returncode

	def waitForTermination(self, timeout=5):
		'''Wait until the timeout for the child to terminate gracefully.
		   Returns True if the child gracefully terminated before the timeout, False otherwise.'''
		if not self.running:
			return True

		startTime = time.time()
		while self.process.poll() is None:
			if time.time() - startTime > timeout:
				return False
			time.sleep(0.1)
			self.flushOutput()
		self.running = False
		self.returncode = self.process.returncode
		return True

	def flushOutput(self):
		'''Wait until al the output from the process has been read and then return'''
		while self.stdout.read() != '':
			pass

	def send(self, text):
		'''Send the given characters to the process with no interpretation'''
		self.stdin.write(text)

	def read(self):
		'''Return a string of all the available output. An empty string is returned when no output is available'''
		self.stdout.read()

	def readLine(self, fullLineOnly=True):
		'''Return a string with the next available line of output from
		   the process. The trailing newline is trimmed.
		   None is returned when no line is available.
		   fullLineOnly=False will return a partial line if it is next in the queue.
		'''
		return self.stdout.readLine(fullLineOnly)

	def readSimple(self, fullLineOnly=True):
		'''Returns a string of all the available output in simplified
		form. An empty string is returned when no output is available.
		Returns a string with:
			- carriage returns removed.
			- Only full lines
		'''
		return self.stdout.readSimple(fullLineOnly)

	def sendLine(self, line):
		'''Send a string to the process, adds a terminating newline'''
		self.send(line + '\n')

	def _checkRegexes(self, regexes, line):
		for i in range(len(regexes)):
			if _debug and line != '':
				print 'checking "%s" against "%s"' % (regexes[i], line)
			if re.match(regexes[i], line) is not None:
				return i
		return -1

	def expect(self, regexes, timeout=5):
		'''Waits for one of the expected regexes to match or the timeout to expire.
		   Returns an index into the regexes sequence on success. Returns -1 on timeout.
		   If multiple matches are found then the first one in regexes is returned.
		'''
		startTime = time.time()

		while time.time() - startTime < timeout:
			line = self.stdout.readSimple()
			if line is None:
				continue # No output this time, wait for next time
			match = self._checkRegexes(regexes, line)
			if match != -1:
				return match
		return -1

	def expectPrompt(self, regexes, timeout=5):
		'''Waits for the expected regex to match or the timeout to
		   expire. The regex will only be matched against the final
		   partial line of the output receieved to date.
		   Returns an index into the regexes sequence on success. Returns -1 on timeout.
		'''
		startTime = time.time()

		while time.time() - startTime < timeout:
			line = self.stdout.readSimple(fullLineOnly=False)
			if line is None:
				continue # No output this time, wait for next time
			match = self._checkRegexes(regexes, line)
			if match != -1:
				return match

		return -1

class TestCase(unittest.TestCase):
	# Setting changable by subclasses for whether the tests will output verbosely or not. The
	# output of the test runner will be modified as appropriate to make it easier to read.
	verbose_output = False

	def setUp(self):
		self.setUp2()
		self.setUp1()
		self.timing.setUp()

	def setUp1(self):
		'''setUp method for the bottom level test class to use. This should be implemented in the test case class
		   instead of putting the setup into the setUp() method as one would in unittest.

		   This method is guarranteed to run upon success of the utility class setup in setUp2().
		'''
		pass

	def setUp2(self):
		'''setUp method for the middle level test utility class to use. This should be implemented in the utility class
		   instead of putting the setup into the setUp() method as one would in unittest.

		   This method is guarranteed to run before the test setup in setUp1(). If this method fails the test will not be run.
		'''
		pass

	def tearDown(self):
		self.timing.tearDown()
		try:
			self.tearDown1()
		except Exception as e:
			self.tearDown2()
			raise e
		self.tearDown2()

	def tearDown1(self):
		'''tearDown method for the bottom level test class to use. This should be implemented in the test case class
		   instead of putting the teardown into the tearDown() method as one would in unittest.

		   This method is guarranteed to run before the utility class teardown in tearDown2().
		'''
		pass

	def tearDown2(self):
		'''tearDown method for the middle level test utility class to use. This should be implemented in the utility class
		   instead of putting the tearDown into the tearDown() method as one would in unittest.

		   This method is guarranteed to run after the test teardown in tearDown1(), even if tearDown1() fails.
		'''
		pass

if __name__ == '__main__':
	class TestTiming(object):
		start = 0
		setup = 0
		teardown = 0
		end = 0

		def __init__(self):
			self.start = time.time()

		def setUp(self):
			self.setup = time.time()

		def tearDown(self):
			self.teardown = time.time()

		def stop(self):
			self.end = time.time()

		def totalTime(self):
			return self.end - self.start

		def setupTime(self):
			return self.setup - self.start

		def tearDownTime(self):
			return self.end - self.teardown

		def testTime(self):
			return self.teardown - self.setup

	class TestResult(unittest.TestResult):
		succesNum = 0
		failureNum = 0
		errorNum = 0
		timings = {}

		def __init__(self):
			unittest.TestResult.__init__(self, sys.stdout, True, 2)

			self.stream = sys.stdout

		def output(self, string, newline=True):
			self.stream.write(string)
			if newline:
				self.stream.write('\n')
			self.stream.flush()

		def testDescription(self, test):
			desc = test.id()
			return desc

		def testVerbose(self, test):
			try:
				return test.verbose_output
			except:
				return False

		def startTest(self, test):
			timing = TestTiming()
			self.timings[test.id()] = timing
			test.timing = timing

			unittest.TestResult.startTest(self, test)

			s = '%s ... ' % self.testDescription(test)
			self.output(s, newline=self.testVerbose(test))

		def stopTest(self, test):
			test.timing.stop()

			unittest.TestResult.stopTest(self, test)

			if self.testVerbose(test):
				format = 'test took %f (%f/%f/%f) seconds\n'
			else:
				format = '  %fs (%f/%f/%f)'

			self.output(format % (test.timing.totalTime(),
					test.timing.setupTime(), test.timing.testTime(),
					test.timing.tearDownTime()))


		def addSuccess(self, test):
			unittest.TestResult.addSuccess(self, test)
			self.output('ok', newline=self.testVerbose(test))

		def addError(self, test, err):
			unittest.TestResult.addError(self, test, err)
			self.output('ERROR', newline=self.testVerbose(test))

		def addFailure(self, test, err):
			unittest.TestResult.addFailure(self, test, err)
			self.output('FAIL', newline=self.testVerbose(test))

		def addSkip(self, test, reason):
			unittest.TestResult.addSkip(self, test, reason)
			self.output('skipped %r' % reason, self.testVerbose(test))

		def addExpectedFailure(self, test, err):
			unittest.TestResult.addExpectedFailure(self, test, err)
			self.output('expected failure', newline=self.testVerbose(test))

		def addUnexpectedSuccess(self, test):
			unittest.TestResult.addUnexpectedSuccess(self, test)
			self.output('unexpected success', newline=self.testVerbose(test))

		def printErrors(self):
			self.output('')

			self.printList('ERROR', self.errors)
			self.printList('FAIL', self.failures)

		def printList(self, prefix, errors):
			for test, error in errors:
				self.output('%s: %s' % (prefix, self.testDescription(test)))
				self.output('%s' % error)

	class TestRunner(unittest.TextTestRunner):
		def _makeResult(self):
			return TestResult()

	def cmd_list(args):
		def list_tests(test_root, test_root_name):
			for test_file in test_root:
				for test_class in test_file:
					for test in test_class:
						print '%s/%s' % (test_root_name, test.id())

		unit_tests = unittest.defaultTestLoader.discover('tests/unit', pattern='*.py', top_level_dir='tests/unit')
		list_tests(unit_tests, 'unit')

		component_tests = unittest.defaultTestLoader.discover('tests/component', pattern='*.py', top_level_dir='tests/component')
		list_tests(component_tests, 'component')

		slow_tests = unittest.defaultTestLoader.discover('tests/slow', pattern='*.py', top_level_dir='tests/slow')
		list_tests(slow_tests, 'slow')

		constrained_tests = unittest.defaultTestLoader.discover('tests/constrained', pattern='*.py', top_level_dir='tests/constrained')
		list_tests(constrained_tests, 'constrained')

		return True

	def cmd_run(args):
		if not args.unit and not args.component and not args.slow and not args.constrained:
			# Default to running all the tests
			args.unit = True
			args.component = True
			args.slow = True
			args.constrained = True

		unittest._lousy_debug = args.debug

		tests = unittest.TestSuite()

		if args.unit:
			unittests = unittest.defaultTestLoader.discover('tests/unit', pattern='*.py', top_level_dir='tests/unit')
			tests.addTest(unittests)
		
		if args.component:
			componenttests = unittest.defaultTestLoader.discover('tests/component', pattern='*.py', top_level_dir='tests/component')
			tests.addTest(componenttests)
		
		if args.slow:
			slowtests = unittest.defaultTestLoader.discover('tests/slow', pattern='*.py', top_level_dir='tests/slow')
			tests.addTest(slowtests)
		
		if args.constrained:
			constrainedtests = unittest.defaultTestLoader.discover('tests/constrained', pattern='*.py', top_level_dir='tests/constrained')
			tests.addTest(constrainedtests)

		if tests.countTestCases() == 0:
			print 'No tests selected to run'
			return True

		runner = TestRunner()
		runner.run(tests)

		return True

	parser = argparse.ArgumentParser(prog='lousy', description='Test Runner with Bug Tracker Integration')
	subcmds = parser.add_subparsers(help='command help')

	list_cmd = subcmds.add_parser('list', help='List all tests')
	list_cmd.set_defaults(func=cmd_list)

	run_cmd = subcmds.add_parser('run', help='Run tests, defaults to all tests')
	run_cmd.add_argument('-u', '--unit', action='store_true', help='Run the unit tests')
	run_cmd.add_argument('-c', '--component', action='store_true', help='Run the component tests')
	run_cmd.add_argument('-s', '--slow', action='store_true', help='Run the slow tests')
	run_cmd.add_argument('-C', '--constrained', action='store_true', help='Run the constrained tests')
	run_cmd.add_argument('-d', '--debug', action='store_true', help='Output debug logging while running tests')
	run_cmd.set_defaults(func=cmd_run)

	# Make it possible for tests to import modules from their parent tests directory
	test_path = os.getcwd() + '/tests'
	sys.path.append(test_path)

	args = parser.parse_args()
	result = args.func(args)

	if not result:
		print "Command failed"
		sys.exit(1)
	else:
		sys.exit(0)
