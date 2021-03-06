#!/usr/bin/env python2.7
# 
# Copyright (C) 2013-2014  Travis Brown (travisb@travisbrown.ca)
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
import copy
import asyncore
import threading
import socket
import struct
import importlib
import traceback
import math
import termios
import pprint

DEFAULT_PORT = 12345
MSG_HEADER_FMT = '!L'

# A hack to allow us to pass the debug setting from lousy as a script to lousy as a library
try:
	_debug = unittest._lousy_debug
except:
	_debug = False

try:
	stubs = unittest._lousy_stubs
except:
	stubs = None

class FrameBufferCell(object):
	'''Class which tracks the value and attributes of a character cell in the
	   framebuffer.
	'''
	char = ''
	attributes = set()

	# Various character attributes
	BOLD = 'Bold'
	UNDERSCORE = 'Underscore'
	BLINK = 'Blink'
	REVERSE = 'Reverse'

	def __init__(self):
		pass

	def __eq__(self, other):
		if self.char != other.char:
			return False

		if self.attributes != other.attributes:
			return False

		return True

	def __ne__(self, other):
		return not self.__eq__(other)

	def __str__(self):
		return '%s(%s)' % (_escapeAscii(self.char), self.attributes)

class FrameBuffer(object):
	'''Opaque class to contain a framebuffer snapshot'''

	def __init__(self, framebuffer):
		self._framebuffer = framebuffer

class DumbTerminal(object):
	'''Base class for all the emulated terminals'''

	framebuffer = None
	modes = {} # Dictionary of dictionaries of methods to call
	mode = 'normal'

	def __init__(self):
		self.initialSettings()

		self.framebuffer = [[FrameBufferCell() for col in range(self.cols)] for row in range(self.rows)]

		self.modes['normal'] = {
				'default': self.i_normal_chars,
				chr(0x00): self.i_ignore,
				chr(0x01): self.i_ignore,
				chr(0x02): self.i_ignore,
				chr(0x03): self.i_ignore,
				chr(0x04): self.i_ignore,
				chr(0x05): self.i_ignore,
				chr(0x06): self.i_ignore,
				'\a': self.i_normal_bell,
				'\b': self.i_normal_backspace,
				'\t': self.i_normal_tab,
				'\n': self.i_normal_newline,
				chr(0x0b): self.i_ignore,
				chr(0x0c): self.i_ignore,
				'\r': self.i_normal_carriageReturn,
				chr(0x0e): self.i_ignore,
				chr(0x0f): self.i_ignore,
				chr(0x10): self.i_ignore,
				chr(0x11): self.i_ignore,
				chr(0x12): self.i_ignore,
				chr(0x13): self.i_ignore,
				chr(0x14): self.i_ignore,
				chr(0x15): self.i_ignore,
				chr(0x16): self.i_ignore,
				chr(0x17): self.i_ignore,
				chr(0x18): self.i_ignore,
				chr(0x19): self.i_ignore,
				chr(0x1a): self.i_ignore,
				chr(0x1b): self.i_ignore,
				chr(0x1c): self.i_ignore,
				chr(0x1d): self.i_ignore,
				chr(0x1e): self.i_ignore,
				chr(0x1f): self.i_ignore,
				chr(0x7f): self.i_ignore,
				}

	def initialSettings(self):
		self.current_row = 0
		self.current_col = 0
		self.rows = 24
		self.cols = 80
		self.tabstop = 8
		self.margin_top = 0
		self.margin_bottom = 23

		# Should the text wrap to the next line when it reaches the end of
		# the line automatically
		self.autowrap = True

		# Should the screen scroll automatically when entering the new line
		# in the bottom-most line of the terminal
		self.autoscroll = True

		# Does a linefeed (\n) character move down one line (False) or down one
		# line and back to the beginning of the line (True)?
		self.linefeed_mode = False

	def dumpCell(self, cell):
		'''Output a single cell with all it's formatting options set'''
		if cell.char == '':
			return ' '
		elif cell.char == '\t':
			return ' '
		else:
			return cell.char

	def dumpFrameBuffer(self):
		'''Print out the characters of the framebuffer as it stands. Note that this is
		   only an approximation as blank cells are written as spaces.
		'''
		s = ''

		# Tens digit of column
		s += '\n   '
		for col in range(self.cols):
			if col % 10 == 0 and col > 0:
				s += '%s' % str((col / 10) % 10)
			else:
				s += ' '

		# Ones digit of column
		s += '\n   '
		for col in range(self.cols):
			s += '%s' % str(col % 10)

		# Top containment line
		s += '\n  +'
		for col in range(self.cols):
			s += '-'
		s += '+\n'

		for row in range(self.rows):
			# Row number
			if row % 10 == 0 and row != 0:
				s += '%s|' % str(row % 100)
			else:
				s += ' %s|' % str(row % 10)

			for col in range(self.cols):
				cell = self.cell(row, col)
				s += self.dumpCell(cell)

			# Row number
			if row % 10 == 0 and row != 0:
				s += '|%s\n' % str(row % 100)
			else:
				s += '| %s\n' % str(row % 10)
		# Bottom containment line
		s += '  +'
		for col in range(self.cols):
			s += '-'
		s += '+\n'

		# Tens digits of column
		s += '   '
		for col in range(self.cols):
			if col % 10 == 0 and col > 0:
				s += '%s' % str((col / 10) % 10)
			else:
				s += ' '

		# Ones digit of column
		s += '\n   '
		for col in range(self.cols):
			s += '%s' % str(col % 10)
		s += '\n'

		sys.stdout.write(s)

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

		if c in self.modes[self.mode]:
			self.modes[self.mode][c](cell, c)
		else:
			self.modes[self.mode]['default'](cell, c)

		if self.current_col == self.cols:
			if self.autowrap:
				self.current_col = 0
				self.current_row += 1
			else:
				self.current_col = self.cols - 1

		if self.current_row == self.margin_bottom + 1:
			if self.autoscroll:
				del self.framebuffer[self.margin_top]
				self.framebuffer.insert(self.margin_bottom, [FrameBufferCell() for col in range(self.cols)])
			self.current_row -= 1

	def i_ignore(self, cell, c):
		'''Ignore the character'''
		pass

	def i_normal_chars(self, cell, c):
		cell.char = c
		self.current_col += 1

	def i_normal_bell(self, cell, c):
		# Interpret the bell character, but don't do anything with it
		pass

	def i_normal_backspace(self, cell, c):
		if self.current_col > 0:
			self.current_col -= 1

	def nextTabstop(self, col):
		# Emulate fixed tab stops
		tabstop = int((col + self.tabstop)/self.tabstop) * self.tabstop
		if tabstop >= self.cols:
			tabstop = self.cols - 1

		return tabstop

	def i_normal_tab(self, cell, c):
		tabstop = self.nextTabstop(self.current_col)

		# If the tabstop would move beyond the edge of the
		# screen and overwrite the last character don't
		# write it.
		for i in range(self.current_col, min(tabstop, self.cols - 1)):
				cell = self.cell(self.current_row, i)
				cell.char = ' '
		self.current_col = tabstop

	def i_normal_newline(self, cell, c):
		self.current_row += 1

		if self.linefeed_mode:
			self.current_col = 0

	def i_normal_carriageReturn(self, cell, c):
		self.current_col = 0

class VT05(DumbTerminal):
	'''Emulate the VT05 according to http://www.vt100.net/docs/vt05-rm/chapter3.html 
	   This isn't expected to be useful, but is rather more a simple 'smart' terminal to work
	   out the emulation inheritance.
	'''

	def __init__(self):
		DumbTerminal.__init__(self)

		self.modes['normal'][chr(0x18)] = self.i_normal_cursorRight
		self.modes['normal'][chr(0x0b)] = self.i_normal_cursorDown
		self.modes['normal'][chr(0x0e)] = self.i_normal_cursorAddress
		self.modes['normal'][chr(0x1a)] = self.i_normal_cursorUp
		self.modes['normal'][chr(0x1d)] = self.i_normal_cursorHome
		self.modes['normal'][chr(0x1e)] = self.i_normal_eraseLine
		self.modes['normal'][chr(0x1f)] = self.i_normal_eraseScreen

		self.modes['cad'] = {
				'default': self.i_cad_address
				}

	def initialSettings(self):
		DumbTerminal.initialSettings(self)

		self.rows = 20
		self.cols = 72

		self.autowrap = False

	def i_normal_cursorRight(self, cell, c):
		if self.current_col < self.cols - 1:
			self.current_col += 1

	def i_normal_cursorDown(self, cell, c):
		if self.current_row < self.rows - 1:
			self.current_row += 1

	def i_normal_cursorUp(self, cell, c):
		if self.current_row > 0:
			self.current_row -= 1

	def i_normal_cursorHome(self, cell, c):
		self.current_col = 0
		self.current_row = 0

	def i_normal_tab(self, cell, c):
		if self.current_col < self.cols - 1:
			cell.char = '\t'

		if self.current_col < 64:
			stops = [0, 8, 16, 24, 32, 40, 48, 56, 64]
			for i in range(len(stops)):
				if self.current_col < stops[i]:
					self.current_col = stops[i]
					return
		elif self.current_col == 71:
			pass
		else: # 64 <= current_col < 71
			self.current_col += 1

	def eraseToEndOfLine(self):
		for i in range(self.current_col, self.cols):
			cell = self.cell(self.current_row, i)
			cell.char = ''

	def i_normal_eraseLine(self, cell, c):
		self.eraseToEndOfLine()

	def i_normal_eraseScreen(self, cell, c):
		self.eraseToEndOfLine()
		for row in range(self.current_row + 1, self.rows):
			for col in range(self.cols):
				cell = self.cell(row, col)
				cell.char = ''

	def i_normal_cursorAddress(self, cell, c):
		self.mode = 'cad'
		self._new_x = None
		self._new_y = None

	def i_cad_address(self, cell, c):
		if self._new_y is None:
			# Capture the new Y location
			y = ord(c) - ord(' ')
			if y < 0 or y >= self.rows:
				# Ignore this input and wait for more
				return
			else:
				self._new_y = y
		else:
			# Capture the new X location
			x = ord(c) - ord(' ')
			if x < 0 or x >= self.cols:
				# Ignore this input and wait for more
				return
			else:
				self._new_x = x

				# We now have both the new x and new y, use them
				self.current_row = self._new_y
				self.current_col = self._new_x
				self.mode = 'normal'

class VT100(DumbTerminal):
	'''VT100 terminal emulator'''

	def __init__(self):
		DumbTerminal.__init__(self)

		self.modes['normal'][chr(0x1b)] = self.i_normal_escape

		self.modes['escape'] = {
				'default': self.i_escape_exit,
				'[': self.i_escape_csi,
				'c': self.i_escape_reset,
				'7': self.i_escape_saveCursor,
				'8': self.i_escape_restoreCursor,
				'D': self.i_escape_cursorDown,
				'E': self.i_escape_nextLine,
				'H': self.i_escape_setTabStop,
				'M': self.i_escape_cursorUp,
				'#': self.i_escape_private,
				}

		self.modes['private'] = {
				'default': self.i_private_exit,
				'8': self.i_private_EFill,
				}

		self.modes['csi'] = {
				'default': self.i_csi_collectParams,
				'f': self.i_csi_placeCursor,
				'g': self.i_csi_tabStopClear,
				'h': self.i_csi_setMode,
				'l': self.i_csi_resetMode,
				'm': self.i_csi_specialGraphics,
				'r': self.i_csi_setTopBottomMargins,
				'A': self.i_csi_moveCursorUp,
				'B': self.i_csi_moveCursorDown,
				'C': self.i_csi_moveCursorForwards,
				'D': self.i_csi_moveCursorBackwards,
				'H': self.i_csi_placeCursor,
				'J': self.i_csi_clearScreen,
				'K': self.i_csi_eraseInLine,
				}
	
	def i_normal_chars(self, cell, c):
		DumbTerminal.i_normal_chars(self, cell, c)

		cell.attributes = set()

		if self.bold:
			cell.attributes.add(FrameBufferCell.BOLD)
		if self.underscore:
			cell.attributes.add(FrameBufferCell.UNDERSCORE)
		if self.blink:
			cell.attributes.add(FrameBufferCell.BLINK)
		if self.reverse:
			cell.attributes.add(FrameBufferCell.REVERSE)

	def nextTabstop(self, col):
		for stop in self.tabstops:
			if stop > col:
				return stop
		# Default as the rightmost cell
		return self.cols - 1

	def dumpCell(self, cell):
		s = ''
		def escWrite(s):
			return chr(0x1b) + s

		attributes = []
		if FrameBufferCell.BOLD in cell.attributes:
			attributes.append('1')
		if FrameBufferCell.UNDERSCORE in cell.attributes:
			attributes.append('4')
		if FrameBufferCell.BLINK in cell.attributes:
			attributes.append('5')
		if FrameBufferCell.REVERSE in cell.attributes:
			attributes.append('7')

		# enable attributes
		if sys.stdout.isatty():
			s += escWrite('[%sm' % ';'.join(attributes))

		s += DumbTerminal.dumpCell(self, cell)

		# reset all attributes
		if sys.stdout.isatty():
			s += escWrite('[0m')

		return s

	def i_normal_escape(self, cell, c):
		# Start an escape sequence
		self.mode = 'escape'

	def i_escape_exit(self, cell, c):
		self.mode = 'normal'
	
	def i_escape_csi(self, cell, c):
		self.mode = 'csi'
		self.csi_params = ''

	def initialSettings(self):
		DumbTerminal.initialSettings(self)

		self.rows = 24
		self.cols = 80
		self.autowrap = False

		# Do line number ignore the configured margins (False) or are
		# they relative to the configured margins (True)
		self.origin_relative = False

		# Character attributes for characters as they come in
		self.bold = False
		self.underscore = False
		self.blink = False
		self.reverse = False
		self.origin_row = 0
		self.origin_col = 0

		# Saved cursor info (if any)
		self.saved = None

		# The tabstops, default state it to have one every 8 chars.
		# Stopping at the rightmost cell is implicit
		self.tabstops = [i for i in range(0, self.cols, 8)]

	def i_escape_reset(self, cell, c):
		self.initialSettings()

		self.mode = 'normal'

	def i_escape_saveCursor(self, cell, c):
		self.saved = {
				'bold'        : self.bold,
				'underscore'  : self.underscore,
				'blink'       : self.blink,
				'reverse'     : self.reverse,
				'current_row' : self.current_row,
				'current_col' : self.current_col,
				}

		self.mode = 'normal'

	def i_escape_restoreCursor(self, cell, c):
		if self.saved is not None:
			self.bold        = self.saved['bold']
			self.underscore  = self.saved['underscore']
			self.blink       = self.saved['blink']
			self.reverse     = self.saved['reverse']
			self.current_row = self.saved['current_row']
			self.current_col = self.saved['current_col']

		self.mode = 'normal'

	def i_escape_cursorDown(self, cell, c):
		self.current_row += 1
		self.mode = 'normal'

	def i_escape_cursorUp(self, cell, c):
		self.current_row = max(self.margin_top - 1, self.current_row - 1)

		if self.current_row == self.margin_top - 1:
			# Scroll down one line
			del self.framebuffer[self.margin_bottom]
			self.framebuffer.insert(self.margin_top, [FrameBufferCell() for col in range(self.cols)])
			self.current_row += 1

		self.mode = 'normal'

	def i_escape_nextLine(self, cell, c):
		self.current_row += 1
		self.current_col = 0
		self.mode = 'normal'

	def i_escape_setTabStop(self, cell, c):
		self.tabstops.append(self.current_col)
		self.tabstops.sort()

		self.mode = 'normal'

	def i_escape_private(self, cell, c):
		self.mode = 'private'

	def i_private_exit(self, cell, c):
		self.mode = 'normal'

	def i_private_EFill(self, cell, c):
		for row in range(self.rows):
			for col in range(self.cols):
				cell = self.cell(row, col)
				cell.char = 'E'

	def i_csi_collectParams(self, cell, c):
		self.csi_params += c

	def i_csi_clearScreen(self, cell, c):
		if self.csi_params == '0' or len(self.csi_params) == 0:
			# Clear from the cursor to the end of the screen
			for col in range(self.current_col, self.cols):
				cell = self.cell(self.current_row, col)
				cell.char = ''
			for row in range(self.current_row + 1, self.rows):
				for col in range(self.cols):
					cell = self.cell(row, col)
					cell.char = ''
		elif self.csi_params == '1':
			# Clear screen from 0,0 to the cursor
			for row in range(self.current_row):
				for col in range(self.cols):
					cell = self.cell(row, col)
					cell.char = ''
			for col in range(self.current_col + 1):
				cell = self.cell(self.current_row, col)
				cell.char = ''
		elif self.csi_params == '2':
			# Clear the entire screen
			for row in range(self.rows):
				for col in range(self.cols):
					cell = self.cell(row, col)
					cell.char = ''

		self.mode = 'normal'

	def i_csi_placeCursor(self, cell, c):
		if self.origin_relative:
			home_row = self.margin_top
			home_col = 0
			rows = self.margin_bottom - self.margin_top + 1
		else:
			home_row = 0
			home_col = 0
			rows = self.rows

		if self.csi_params == '' or self.csi_params == ';':
			# Received ';' so go to the origin
			self.current_row = home_row
			self.current_col = home_col
		else:
			# Assume 'l;c'
			coords = self.csi_params.split(';')
			new_row = max(int(coords[0]) - 1, 0)
			new_col = max(int(coords[1]) - 1, 0)

			if new_col < self.cols and new_row < rows:
				# Ignore requests to move outside the allowable view
				self.current_row = new_row + home_row
				self.current_col = new_col + home_col

		self.mode = 'normal'

	def i_csi_tabStopClear(self, cell, c):
		if self.csi_params == '' or self.csi_params == '0':
			try:
				del self.tabstops[self.tabstops.index(self.current_col)]
			except:
				# The tabstop wasn't previously set as a tabstop, all is fine
				pass
		elif self.csi_params == '3':
			self.tabstops = []

		self.mode = 'normal'

	def decodeTermMode(self, mode, value):
		# Decode the mode and set the value as appropriate
		# Children of this class should override this method as
		# appropriate, making sure to call the superclass for any
		# unknown modes.
		if mode == '20':
			self.linefeed_mode = value
		elif mode == '7':
			self.autowrap = value
		elif mode == '6':
			self.origin_relative = value

			if value:
				self.origin_row = self.margin_top
				self.origin_col = 0
			else:
				self.origin_row = 0
				self.origin_col = 0
			self.current_row = self.origin_row
			self.current_col = self.origin_col
		else:
			print 'Unsupported mode %s' % mode

	def i_csi_setMode(self, cell, c):
		modes = self.csi_params.split(';')
		for mode in modes:
			if len(mode) == 0:
				continue

			self.decodeTermMode(mode, True)

		self.mode = 'normal'

	def i_csi_resetMode(self, cell, c):
		modes = self.csi_params.split(';')
		for mode in modes:
			if len(mode) == 0:
				continue

			self.decodeTermMode(mode, False)

		self.mode = 'normal'

	def i_csi_specialGraphics(self, cell, c):
		attributes = self.csi_params.split(';')
		if len(attributes) == 0:
			attributes = ['0']

		for attr in attributes:
			if attr == '0':
				self.bold = False
				self.underscore = False
				self.blink = False
				self.reverse = False

			if attr == '1':
				self.bold = True
			if attr == '4':
				self.underscore = True
			if attr == '5':
				self.blink = True
			if attr == '7':
				self.reverse = True

		self.mode = 'normal'

	def i_csi_setTopBottomMargins(self, cell, c):
		coords = self.csi_params.split(';')

		if self.origin_relative:
			top = self.margin_top
			bottom = self.margin_bottom - self.margin_top
			num_rows = self.margin_bottom - self.margin_top + 1
		else:
			top = 0
			bottom = self.rows - 1
			num_rows = self.rows

		if len(coords) >= 1 and coords[0] != '':
			top = int(coords[0]) - 1
		if len(coords) >= 2 and coords[1] != '':
			bottom = int(coords[1]) - 1

		if bottom <= top \
		   or bottom >= num_rows \
		   or top < 0:
			# The scrolling region must be at least two
			# lines and other cases are errors
			self.mode = 'normal'
			print 'exiting early %d %d %d %d %d' % (top, bottom, self.margin_top, self.margin_bottom, num_rows)
			return

		self.margin_top = self.origin_row + top
		self.margin_bottom = self.origin_row + bottom

		# If we are in relative origin mode we've reduced out window
		# size, adjust that before moving the cursor
		if self.origin_relative:
			self.origin_row = self.margin_top

		self.current_row = self.origin_row
		self.current_col = self.origin_col

		self.mode = 'normal'

	def i_csi_moveCursorUp(self, cell, c):
		if self.csi_params == '':
			distance = 1
		else:
			distance = int(self.csi_params)

		if distance == 0:
			distance = 1

		self.current_row = max(self.margin_top, self.current_row - distance)

		self.mode = 'normal'

	def i_csi_moveCursorDown(self, cell, c):
		if self.csi_params == '':
			distance = 1
		else:
			distance = int(self.csi_params)

		if distance == 0:
			distance = 1

		self.current_row = min(self.margin_bottom, self.current_row + distance)

		self.mode = 'normal'

	def i_csi_moveCursorForwards(self, cell, c):
		if self.csi_params == '':
			distance = 1
		else:
			distance = int(self.csi_params)

		if distance == 0:
			distance = 1

		self.current_col = min(self.cols - 1, self.current_col + distance)

		self.mode = 'normal'

	def i_csi_moveCursorBackwards(self, cell, c):
		if self.csi_params == '':
			distance = 1
		else:
			distance = int(self.csi_params)

		if distance == 0:
			distance = 1

		self.current_col = max(0, self.current_col - distance)

		self.mode = 'normal'

	def i_csi_eraseInLine(self, cell, c):
		if self.csi_params == '0' or len(self.csi_params) == 0:
			# Erase from current position to end of line
			for col in range(self.current_col, self.cols):
				cell = self.cell(self.current_row, col)
				cell.char = ''
		elif self.csi_params == '1':
			# Erase from beginning of line to current position
			for col in range(self.current_col + 1):
				cell = self.cell(self.current_row, col)
				cell.char = ''
		elif self.csi_params == '2':
			# Erase entire line
			for col in range(self.cols):
				cell = self.cell(self.current_row, col)
				cell.char = ''

		self.mode = 'normal'

class TypicalTty(VT100):
	'''A pseudo-xterm terminal which supports all the most common escape codes'''

	def __init__(self):
		VT100.__init__(self)

		self.modes['escape'][']'] = self.i_escape_osc

		self.modes['osc'] = {
				'default' : self.i_osc_collectParams,
				'\007': self.i_osc_process,
				}

	def initialSettings(self):
		VT100.initialSettings(self)

		self.window_title = ''
		self.icon_name = ''

	def i_escape_osc(self, cell, c):
		self.mode = 'osc'
		self.osc_params = ''

	def i_osc_collectParams(self, cell, c):
		self.osc_params += c

	def i_osc_set_icon(self, args):
		self.icon_name = args

	def i_osc_set_window(self, args):
		self.window_title = args

	def i_osc_set_icon_and_window(self, args):
		self.i_osc_set_icon(args)
		self.i_osc_set_window(args)

	def i_osc_process(self, cell, c):
		cmds = {
				'0': self.i_osc_set_icon_and_window,
				'1': self.i_osc_set_icon,
				'2': self.i_osc_set_window,
				}

		cmd, args = self.osc_params.split(';', 1)

		if cmd in cmds:
			cmds[cmd](args)
		else:
			print 'Unknown osc command %s' % cmd

		self.mode = 'normal'

class Vtty(object):
	'''Vtty is a terminal emulator which interprets the output of a process and keeps a
	   virtual framebuffer which can be examined to confirm process output.
	'''

	emulation = None

	supported = {
			'dumb': DumbTerminal,
			'vt05': VT05,
			'vt100': VT100,
			'typical': TypicalTty,
			}


	def __init__(self, emulation='vt100'):
		'''emulation is the terminal emulator featureset and control codes to emulate.
		   Valid values are:
		   dumb
		   vt05
		   vt100
		   typical - supports all the common set of escape codes
		'''
		if emulation is True:
			emulation = 'vt100'

		if emulation in self.supported:
			self.emulation = self.supported[emulation]()
		else:
			raise ValueError('%s is not a supported terminal emulation type' % emulation)

	def append(self, input):
		'''Interpret the given stream of bytes to make their modification to the current
		   state of the virtual terminal.
		'''
		for c in input:
			self.emulation.interpret(c)

	def cell(self, row, col):
		return self.emulation.cell(row, col)

	def string(self, row, col, size):
		'''Return the string by reading from (row, col) rightwards
		   size cells. Ignores attributes. If the cell is out of
		   range nothing will be added to the returned string. Does
		   not wrap around to get more characters.
		'''
		s = ''
		for c in range(col, col + size):
			cell = self.cell(row, c)
			if cell is not None:
				s += cell.char
		return s

	def cursorPosition(self):
		'''Return the 2-tuple with the current cursor position'''
		return (self.emulation.current_row, self.emulation.current_col)

	def cols(self):
		'''Returns the number of columns in the virtual terminal'''
		return self.emulation.cols

	def rows(self):
		'''Returns the number of rows in the virtual terminal'''
		return self.emulation.rows

	def snapShotScreen(self, forcePrint=False):
		'''Returns an opaque object which is a snapshot of the virtual
		   screen contents. This object can be compared with other
		   snapshots, but will not contain the terminal state (such as
		   in progress state changes).
		'''
		if _debug or forcePrint:
			self.emulation.dumpFrameBuffer()
		return FrameBuffer(copy.deepcopy(self.emulation.framebuffer))

def _escapeAscii(string):
	'''Given an ascii string escape all non-printable characters to be printable'''

	# encoding doesn't work for \t \n and \r so we must do it ourselves
	def escape_whitespace(character):
		if character == '\t':
			return '\\t'
		elif character == '\033':
			return '^['
		else:
			return character

	string = ''.join(map(escape_whitespace, string))
	return string.encode('unicode_escape')

class ProcessPipe(object):
	'''File object to interact with processes.
	   Any output from the process will be output with a prefix and stored until
	   queried by the test.
	   '''

	prefix = ''
	closed = False
	buffer = ''
	_mirror = None

	def __init__(self):
		self.pipes = os.pipe()
		self._setCloseExec(self.pipes[0])
		self._setCloseExec(self.pipes[1])

	def setPrefix(self, prefix):
		self.prefix = prefix

	def mirror(self, newMirror):
		'''A mirror is an object which the ProcessPipe calls obj.append() on with the
		   newly read data. Useful for alternative interpretations of the output.
		'''
		self._mirror = newMirror

	def fileno(self):
		return self.pipes[self._direction]

	def _setCloseExec(self, fd):
		flags = fcntl.fcntl(fd, fcntl.F_GETFD)
		fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

	def _setNonBlocking(self, fd):
		flags = fcntl.fcntl(fd, fcntl.F_GETFL)
		fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

	def write(self, string):
		'''Returns number of bytes successfully written'''
		lines = _escapeAscii(string).split('\n')
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
			timeout = 0.05

		ready, _, _ = select.select([self.pipes[self._fileno]], [], [], timeout)
		if len(ready) == 0:
			output = self.buffer
			self.buffer = ''
			return output

		output = os.read(self.pipes[self._fileno], 102400)

		if self._mirror is not None:
			self._mirror.append(output)

		if len(output) > 0:
			lines = _escapeAscii(output).split('\\n')
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

	def __init__(self, rows=24, cols=80):
		self.pipes = os.openpty()
		self._setTtySize(self.pipes[0], rows, cols)
		self._setCloseExec(self.pipes[0])

	def _setTtySize(self, fd, rows, cols):
		# pack a struct winsize
		arg = struct.pack('@HHHH', rows, cols, 0, 0)
		fcntl.ioctl(fd, termios.TIOCSWINSZ, arg)

class Process(object):
	'''Class for interacting with processes'''

	def __init__(self, command, shell=False, pty=False, ptySize=(24, 80)):
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

		   ptySize is the tuple (rows, cols) for the size of the newly created pty.
		   Defaults to (24, 80).

		   If shell is True then the command list is converted into a space separate string
		   to be interpretted by the shell.
		'''

		if pty == True or type(pty) == type('string'):
			self.stdin = PtyProcessPipe(ptySize[0], ptySize[1])
			self.stdout = self.stdin
			self.stderr = self.stdin

			if pty != True:
				self.vty = Vtty(pty)
				self.stdout.mirror(self.vty)
		else:
			self.stdin = InProcessPipe()
			self.stdout = OutProcessPipe()
			self.stderr = OutProcessPipe()
			self.vty = None

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
			self.flushOutput()
		self.running = False
		self.returncode = self.process.returncode
		return True

	def flushOutput(self):
		'''Wait until all the output from the process has been read and then return'''
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
				print 'checking "%s" against "%s"' % (regexes[i], _escapeAscii(line))
			if re.search(regexes[i], line) is not None:
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

def _readStubMessage(sock):
	'''Given the socket read the next stub message and return it to be parsed.

	   The message format is simple, first a four byte integer with the
	   length of the message, then the message itself of that length.
	'''
	buf = sock.recv(struct.calcsize(MSG_HEADER_FMT))
	size = struct.unpack(MSG_HEADER_FMT, buf)[0]

	msg = sock.recv(size)
	return msg

class Stub(asyncore.dispatcher):
	'''This is the base class of the Stub objects. It is intended that a
	   user will subclass this to add the methods they wish to stub out
	   with the logic to do so.

	   When you subclass this be sure to set, either at initialization or
	   as part of __init__, self.type to the string you intend to
	   register this class for.
	'''
	in_buf = None
	out_buf = None
	read_ready = None # Is there data to be read
	write_done = None # There is no more data to write
	lock = None
	_disconnect = False

	def __init__(self, sock=None, map=None):
		asyncore.dispatcher.__init__(self, sock, map)
		self.read_ready = threading.Event()
		self.write_done = threading.Event()
		self.lock = threading.Lock()
		self.in_buf = []
		self.out_buf = []

	def writable(self):
		if len(self.out_buf) > 0:
			return True
		else:
			if self._disconnect:
				self.del_channel()
				self.close()

			self.write_done.set()
			return False

	def readable(self):
		return not self._disconnect

	def handle_write(self):
		if len(self.out_buf) == 0:
				return

		if _debug:
			print 'Stub sending message "%s"' % _escapeAscii(self.out_buf[0])

		self.send(struct.pack(MSG_HEADER_FMT, len(self.out_buf[0])))
		bytes_sent = self.send(self.out_buf[0])
		if bytes_sent == len(self.out_buf[0]):
			del self.out_buf[0]
		else:
			self.out_buf[0] = self.out_buf[0][bytes_sent:]

	def handle_read(self):
		ready = self.socket.recv(100, socket.MSG_PEEK)
		if len(ready) < 4:
			# Not enough data to decode yet, wait a bit
			if not ready:
				# socket was closed by the other end
				self.close()
			return

		self.lock.acquire()
		msg = _readStubMessage(self.socket)

		if _debug:
			print 'Stub received message "%s"' % msg

		if not self.consume_read(msg):
			self.in_buf.append(msg)
			self.read_ready.set()

		self.lock.release()

	def disconnect(self):
		self._disconnect = True
		self.stubcentral.trigger()

	def consume_read(self, msg):
		'''This method is called when a message has been received. If
		   this method returns False then the message will be queued
		   on the internal queue waiting for a read() call. True and
		   the message will be discarded under the assumption that
		   the Stub class has handled the message appropriately.

		   The intention is that a Stub which has intelligence may
		   interpret the message and provide a response without
		   waiting for the test input if appropriate.
		'''
		return False

	def read(self, timeout=5):
		'''Read the next message sent by the far side of the stub.
		Returns an empty string if nothing was received.
		'''
		self.read_ready.wait(timeout)
		self.lock.acquire()

		if len(self.in_buf) == 0:
			self.lock.release()
			return ''

		buf = self.in_buf[0]
		del self.in_buf[0]
		self.read_ready.clear()
		self.lock.release()

		return buf

	def write(self, msg):
		'''Add the given message to be sent to the far side stub
		as soon as possible.
		'''
		if _debug:
			print 'Stub adding message to write queue "%s"' % _escapeAscii(msg)
		self.out_buf.append(msg)
		self.write_done.clear()
		self.stubcentral.trigger()

	def flush(self, timeout=5):
		'''Wait until the write queue is empty or the timeout has elapsed.
		'''
		self.write_done.wait(timeout)

class SimpleStub(Stub):
	'''This is a Stub which acts as a dumb, asynchrounous datapipe. 
	   It will store any messages received from the far end stub until a
	   read() call is provided. Literal text is sent to the far end using
	   the write() method.

	   Each call will return a single message. If there are more messages
	   then subsequent read()/write() calls are required.

	   You shouldn't really inherit from this class.
	   '''
	type = 'SimpleStub'

class TestCase(unittest.TestCase):
	# Setting changable by subclasses for whether the tests will output verbosely or not. The
	# output of the test runner will be modified as appropriate to make it easier to read.
	verbose_output = False

	def __init__(self, methodName='runTest'):
		unittest.TestCase.__init__(self, methodName)

		self.tearDown1Called = None
		self.tearDown2Called = None
		self.addCleanup(self.tearDown)

		self._FrameBufferLooseEquality = False
		self.addTypeEqualityFunc(type(FrameBuffer('')), self._assertEqual_FrameBuffer)

	def _assertEqual_FrameBuffer(self, a, b, msg=None):
		a = a._framebuffer
		b = b._framebuffer

		failmsg = ''
		errors = 0
		max_errors = 10

		if len(a) != len(b) or len(a[0]) != len(b[0]):
			raise self.failureException('Framebuffer sizes do not match (%d x %d) vs (%d x %d): %s' %
					(len(a), len(a[0]), len(b), len(b[0]), msg))

		for row in range(len(a)):
			for col in range(len(a[row])):
				A = a[row][col]
				B = b[row][col]

				if self._FrameBufferLooseEquality:
					if A.char == '':
						A.char = ' '
					if B.char == '':
						B.char = ' '
				if A != B and errors < max_errors:
					failmsg += '(%d, %d) "%s" != "%s"; ' % (row, col, a[row][col], b[row][col])
					errors += 1

		if errors >= max_errors:
			failmsg += '(other errors elided)'

		if failmsg != '':
			if msg is not None:
				failmsg += ': %s' % msg

			raise self.failureException(failmsg)

	def setUp(self):
		self.tearDown2Called = False
		self.setUp2()

		self.tearDown1Called = False
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
			if self.tearDown1Called is False:
				self.tearDown1()
				self.tearDown1Called = True
		except Exception as e:
			if self.tearDown2Called is False:
				self.tearDown2()
				self.tearDown2Called = True
			raise e
		if self.tearDown2Called is False:
			self.tearDown2()
			self.tearDown2Called = True

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

	class ProtoStub(asyncore.dispatcher):
		# This is a stub connection after the new socket has been
		# accept()ed from StubListener, but before any data has been
		# read which will let us determine the stub class to
		# instantiate.

		def writable(self):
			return False

		def handle_read(self):
			# Remove ourself from the global list of sockets to
			# watch and send our socket to StubCentral to be
			# reborn as a new Stub class according to its type.
			buf = self.socket.recv(100, socket.MSG_PEEK)

			if len(buf) >= struct.calcsize(MSG_HEADER_FMT):
				self.del_channel()
				self.stub._new_stub(self.socket)
			elif not buf:
				# Socket has been closed by the far end
				self.close()

	class StubListener(asyncore.dispatcher):
		# This is a class which listens for new stub connections
		def __init__(self, stubcentral):
			asyncore.dispatcher.__init__(self)

			self.stub = stubcentral

			self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
			self.port = DEFAULT_PORT
			while True:
				try:
					self.bind(('localhost', self.port))
					break
				except:
					self.port += 1
			self.listen(5)

		def handle_accept(self):
			sock, address = self.accept()
			protostub = ProtoStub(sock)
			protostub.stub = self.stub


		def writable(self):
			return False

	class StubPoker(asyncore.dispatcher):
		# This is dispatcher used to get out of the select loop. It
		# uses a pair of sockets to be portable

		def __init__(self):
			self.s1, self.s2 = socket.socketpair()

			asyncore.dispatcher.__init__(self, sock = self.s1)

		def writable(self):
			return False

		def handle_read(self):
			# Throw away the data since it doesn't matter and has served its purpose
			s = self.recv(100)

		def trigger(self):
			self.s2.send('a')

	class StubCentral(threading.Thread):
		'''This is an asyncore based server which provides a TCP
		   based method to control external programs. The intended
		   usecase is to have written stub classes/functions in the
		   language of the application being tested and use some
		   simple stub functionality to control that from the test
		   framework. This is the central clearing house for
		   registering, creating and finding Stub object.
		'''

		_lock = None
		_port = None
		_listener = None
		_poker = None
		_classes = {}
		_objects = {}
		_running = True
		_ready = None
		_newest = None
		_stub_created = None

		def __init__(self):
			threading.Thread.__init__(self, name='StubCentral')

			self._lock = threading.Lock()
			self._ready = threading.Event()
			self._stub_created = threading.Event()

		def _init(self):
			self._listener = StubListener(self)
			self._port = self._listener.port
			self._poker = StubPoker()
			self._ready.set()

		def _new_stub(self, sock):
			# Handle a new connection and create an object of
			# the appropriate stub class.
			msg = _readStubMessage(sock)

			type, id = msg.split(',')

			if id in self._objects:
				print 'Error: Stub object "%s" of type "%s" already exists' % (id, type)

			create_callback = None
			if type in self._classes :
				constructor, create_callback = self._classes[type]
				stub = constructor(sock)
			else:
				# Unknown type, create a simple stub
				stub = SimpleStub(sock)
				if 'default' in self._classes:
					_, create_callback = self._classes['default']
					type = 'SimpleStub'

			stub.stubcentral = self

			if create_callback is not None:
				create_callback(stub, type)

			self._lock.acquire()
			self._newest = stub
			self._stub_created.set()
			self._lock.release()

		def waitForStub(self, type=None, timeout=5):
			'''Wait until the timeout expires or a stub of the
			   given class is created. Return the object of that
			   stub.

			   If type is None then return the next stub to be
			   created.
			'''
			startTime = time.time()

			timeLeft = timeout - (time.time() - startTime)
			while timeLeft > 0:
				self._stub_created.wait(timeLeft)

				with self._lock:
					self._stub_created.clear()

					if type is None:
						return self._newest
					elif self._newest.type == type:
						return self._newest

				timeLeft = timeLeft - (time.time() - startTime)

		def newest(self):
			self._lock.acquire()
			stub = self._newest
			self._lock.release()

			return stub

		def add_class(self, classname, class_obj, create_callback=None):
			'''Add a stub callback class. When a new stub
			   registers itself with lousy if the class name
			   exists then the created object will be created
			   with that class instead of SimpleStub.

			   create_callback is called, if not None, when a new
			   instance of the given class object is created.
			   This allows the test to acknowledge the creation
			   and start interacting with the new object. This
			   callable is called with the new object as the first
			   argument and the classname string as the second. A
			   special argument of 'default' can be used with
			   None as the class_obj to set the callback called
			   when a SimpleStub is created. In this case
			   'SimpleStub' will be the type string returned to
			   the (optional) callback.

			   This method can also be used to reset the class to
			   use. This is useful if you have multiple tests
			   which use the same stubs but you want different
			   mock objects for each test.
			'''
			if classname == 'SimpleStub':
				self._classes[classname] = (SimpleStub, create_callback)
			else:
				self._classes[classname] = (class_obj, create_callback)

		def trigger(self):
			# We've been triggered, so we need to exit the
			# select loop and reprocess.
			self._poker.trigger()

		def stop(self):
			self._lock.acquire()
			self._running = False
			self._lock.release()

			if self.is_alive():
				self.trigger()

		def ready(self):
			'''Ensure that the stub protocol is ready for use.
			'''
			if not self._ready.is_set():
				self.start()
				self._ready.wait()

		def port(self):
			'''Return the port needed to connect stubs to this
			   instance of lousy. This port will always be bound
			   to IPv4 localhost on the specified port.
			'''
			self.ready()
			return self._port

		def run(self):
			# We don't create the socket until we are run
			# because many tests won't need the Stub at all and
			# it'd be wasteful to create them otherwise.
			self._lock.acquire()
			if self._port is None:
				self._init()

			self._running = True
			self._lock.release()

			still_running = True
			while still_running:
				asyncore.loop(timeout=5, use_poll=True, count=1)

				self._lock.acquire()
				still_running = self._running
				self._lock.release()

	# A little class which wraps a file and prepends the date and time to every line.
	class DatedFileWrapper(object):
		date_format = '%Y-%m-%d %H:%M:%S%%s | '

		def __init__(self, file):
			self.fd = file

		def _get_time(self):
			now = time.time()
			t = time.localtime(now)
			s = time.strftime(self.date_format, t)

			# Apply the factional seconds
			fractional_secs = math.modf(now)[0]
			fractional_secs = '%f' % fractional_secs
			fractional_secs = fractional_secs.lstrip('0')

			s = s % fractional_secs

			return s

		def write(self, s):
			if s != '\n':
				self.fd.write(self._get_time())
			self.fd.write(s)

		def __getattr__(self, name):
			return getattr(self.fd, name)

	# Given a TestSuite of TestSuits of TestClasses, return a list of only those tests whose ID
	# matches the given regex.
	#
	# Returns an empty list if none match
	def filter_tests(test_root, type, regex):
		if regex == '':
			regex = '.+'

		result = []

		for test_file in test_root:
			try:
				for test_class in test_file:
					for test in test_class:
						if re.search(regex, type + '/' + test.id()) is not None:
							result.append(test)
			except TypeError:
				print 'Unable to import test file:'
				try:
					importlib.import_module(test_class._testMethodName, type)
				except Exception as e:
					# Skip the frames inside Lousy
					stack_depth = len(traceback.extract_tb(sys.exc_info()[2]))
					traceback.print_exc(limit=stack_depth - 2)
		return result

	def cmd_list(args):
		unit_tests = unittest.defaultTestLoader.discover('tests/unit', pattern='*.py', top_level_dir='tests/unit')
		for test in filter_tests(unit_tests, 'unit', args.re):
			print 'unit/%s' % test.id()

		component_tests = unittest.defaultTestLoader.discover('tests/component', pattern='*.py', top_level_dir='tests/component')
		for test in filter_tests(component_tests, 'component', args.re):
			print 'component/%s' % test.id()

		slow_tests = unittest.defaultTestLoader.discover('tests/slow', pattern='*.py', top_level_dir='tests/slow')
		for test in filter_tests(slow_tests, 'slow', args.re):
			print 'slow/%s' % test.id()

		constrained_tests = unittest.defaultTestLoader.discover('tests/constrained', pattern='*.py', top_level_dir='tests/constrained')
		for test in filter_tests(constrained_tests, 'constrained', args.re):
			print 'constrained/%s' % test.id()

		return True

	def cmd_run(args):
		if not args.unit and not args.component and not args.slow and not args.constrained:
			# Default to running all the tests
			args.unit = True
			args.component = True
			args.slow = True
			args.constrained = True

		unittest._lousy_debug = args.debug
		global _debug
		_debug = args.debug

		sys.stdout = DatedFileWrapper(sys.stdout)

		if stubs is None:
			# This instance is run as a script, so ensure that
			# lousy as a module has a copy of the StubCentral
			unittest._lousy_stubs = StubCentral()

		tests = unittest.TestSuite()

		if args.unit:
			unittests = unittest.defaultTestLoader.discover('tests/unit', pattern='*.py', top_level_dir='tests/unit')
			tests.addTests(filter_tests(unittests, 'unit', args.re))
		
		if args.component:
			componenttests = unittest.defaultTestLoader.discover('tests/component', pattern='*.py', top_level_dir='tests/component')
			tests.addTests(filter_tests(componenttests, 'component', args.re))
		
		if args.slow:
			slowtests = unittest.defaultTestLoader.discover('tests/slow', pattern='*.py', top_level_dir='tests/slow')
			tests.addTests(filter_tests(slowtests, 'slow', args.re))
		
		if args.constrained:
			constrainedtests = unittest.defaultTestLoader.discover('tests/constrained', pattern='*.py', top_level_dir='tests/constrained')
			tests.addTests(filter_tests(constrainedtests, 'constrained', args.re))

		if tests.countTestCases() == 0:
			print 'No tests selected to run'
			return True

		runner = TestRunner()
		runner.run(tests)

		unittest._lousy_stubs.stop()

		return True

	parser = argparse.ArgumentParser(prog='lousy', description='Test Runner with Bug Tracker Integration')
	subcmds = parser.add_subparsers(help='command help')

	list_cmd = subcmds.add_parser('list', help='List all tests')
	list_cmd.add_argument('re', nargs='?', default='.+', help='Regex used to filter returned tests')
	list_cmd.set_defaults(func=cmd_list)

	run_cmd = subcmds.add_parser('run', help='Run tests, defaults to all tests')
	run_cmd.add_argument('-u', '--unit', action='store_true', help='Run the unit tests')
	run_cmd.add_argument('-c', '--component', action='store_true', help='Run the component tests')
	run_cmd.add_argument('-s', '--slow', action='store_true', help='Run the slow tests')
	run_cmd.add_argument('-C', '--constrained', action='store_true', help='Run the constrained tests')
	run_cmd.add_argument('-d', '--debug', action='store_true', help='Output debug logging while running tests')
	run_cmd.add_argument('re', nargs='?', default='.+', help='Regex used to filter run tests')
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
