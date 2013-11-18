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
import pprint

class LousyTestCase(unittest.TestCase):
	pass

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

	runner = unittest.TextTestRunner(verbosity=2)
	runner.run(tests)

	return True

if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog='lousy', description='Test Runner with Bug Tracker Integration')
	subcmds = parser.add_subparsers(help='command help')

	list_cmd = subcmds.add_parser('list', help='List all tests')
	list_cmd.set_defaults(func=cmd_list)

	run_cmd = subcmds.add_parser('run', help='Run tests, defaults to all tests')
	run_cmd.add_argument('-u', '--unit', action='store_true', help='Run the unit tests')
	run_cmd.add_argument('-c', '--component', action='store_true', help='Run the component tests')
	run_cmd.add_argument('-s', '--slow', action='store_true', help='Run the slow tests')
	run_cmd.add_argument('-C', '--constrained', action='store_true', help='Run the constrained tests')
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