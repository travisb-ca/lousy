# Tests of the various emulated terminal classes

import lousy

class TerminalTestCase(lousy.TestCase):
	def assertCellChar(self, row, col, char):
		cell = self.vty.cell(row, col)
		self.assertIsNotNone(cell)
		msg = '"%s" != "%s" at cell (%d, %d)' % (char, cell.char, row, col)
		self.assertEqual(cell.char, char, msg)

class DumbTerminalTests(TerminalTestCase):
	''' Test the DumbTerminal class '''
	def setUp1(self):
		self.vty = lousy.DumbTerminal()

	def tearDown1(self):
		pass

	def test_basicEcho(self):
		self.vty.interpret('a')
		self.assertCellChar(0, 0, 'a')

		self.vty.interpret('s')
		self.assertCellChar(0, 1, 's')

		self.vty.interpret('d')
		self.assertCellChar(0, 2, 'd')

		self.vty.interpret('f')
		self.assertCellChar(0, 3, 'f')

	def test_echoWrapAround(self):
		for i in range(self.vty.cols):
			self.vty.interpret('a')

		self.assertCellChar(1, 0, '')

		self.vty.interpret('b')
		self.assertCellChar(1, 0, 'b')

	def test_echoNewLine(self):
		self.vty.interpret('1')
		self.vty.interpret('\n')
		self.vty.interpret('2')

		self.assertCellChar(0, 0, '1')
		self.assertCellChar(1, 1, '2')

	def test_echoCarriageReturn(self):
		self.vty.interpret('1')
		self.vty.interpret('2')
		self.vty.interpret('\r')
		self.vty.interpret('3')

		self.assertCellChar(0, 0, '3')
		self.assertCellChar(0, 1, '2')

	def test_echoScrollOffScreen(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for i in range(self.vty.rows - 1):
			self.vty.interpret(s[i])
			self.vty.interpret('\r')
			self.vty.interpret('\n')
		self.vty.interpret(s[self.vty.rows - 1])

		for i in range(self.vty.rows):
			self.assertCellChar(i, 0, s[i])

		self.vty.interpret('\r')
		self.vty.interpret('\n')
		self.vty.interpret('1')

		for i in range(self.vty.rows - 1):
			self.assertCellChar(i, 0, s[i + 1])

		self.assertCellChar(self.vty.rows - 1, 0, '1')

	def test_tabStops(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for i in range(self.vty.cols / self.vty.tabstop):
			self.vty.interpret(s[i])
			self.vty.interpret('\t')
		overwrite_char = s[self.vty.cols / self.vty.tabstop + 1]
		self.vty.interpret(overwrite_char)

		for i in range(self.vty.cols):
			if i % self.vty.tabstop == 0:
				self.assertCellChar(0, i, s[i / self.vty.tabstop])
			elif i == self.vty.cols - 1:
				self.assertCellChar(0, i, overwrite_char)
			else:
				self.assertCellChar(0, i, ' ')

	def test_ignoreOtherControlChars(self):
		for i in range(self.vty.cols):
			self.vty.interpret('a')

		for i in range(0x20):
			c = chr(i)
			if c not in '\a\b\t\n\r':
				self.vty.interpret(c)

		for i in range(self.vty.cols):
			self.assertCellChar(0, i, 'a')

	def test_backspace(self):
		self.vty.interpret('a')
		self.vty.interpret('b')
		self.vty.interpret('c')
		self.vty.interpret('\b')
		self.vty.interpret('\b')
		self.vty.interpret('d')

		self.assertCellChar(0, 0, 'a')
		self.assertCellChar(0, 1, 'd')
		self.assertCellChar(0, 2, 'c')

class VT05Tests(TerminalTestCase):
	''' Test the VT05 class '''
	def setUp1(self):
		self.vty = lousy.VT05()

	def tearDown1(self):
		pass

	def test_cursorRight(self):
		self.vty.interpret('a')
		self.vty.interpret('a')
		self.vty.interpret('a')
		self.vty.interpret('a')

		self.vty.interpret('\r')
		self.vty.interpret(chr(0x18))
		self.vty.interpret('b')
		self.vty.interpret(chr(0x18))
		self.vty.interpret('b')

		self.assertCellChar(0, 0, 'a')
		self.assertCellChar(0, 1, 'b')
		self.assertCellChar(0, 2, 'a')
		self.assertCellChar(0, 3, 'b')

	def test_cursorDown(self):
		self.vty.interpret('a')
		self.vty.interpret('\r')
		self.vty.interpret(chr(0x0b))
		self.vty.interpret('b')
		self.vty.interpret('\r')
		self.vty.interpret(chr(0x0b))

		self.assertCellChar(0, 0, 'a')
		self.assertCellChar(1, 0, 'b')

	def test_cursorUp(self):
		self.vty.interpret('a')
		self.vty.interpret('\r')
		self.vty.interpret('\n')
		self.vty.interpret('b')
		self.vty.interpret('\r')
		self.vty.interpret(chr(0x1a))
		self.vty.interpret('c')

		self.assertCellChar(0, 0, 'c')
		self.assertCellChar(1, 0, 'b')

	def test_cursor_Home(self):
		for i in range(10):
			self.vty.interpret('a')
			self.vty.interpret('\n')

		self.vty.interpret(chr(0x1d))
		self.vty.interpret('b')

		for i in range(10):
			if i == 0:
				c = 'b'
			else:
				c = 'a'

			self.assertCellChar(i, i, c)

	def test_tabStop(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for i in range(20):
			self.vty.interpret(s[i])
			self.vty.interpret('\t')

		self.assertCellChar(0, 0, s[0])
		self.assertCellChar(0, 8, s[1])
		self.assertCellChar(0, 16, s[2])
		self.assertCellChar(0, 24, s[3])
		self.assertCellChar(0, 32, s[4])
		self.assertCellChar(0, 40, s[5])
		self.assertCellChar(0, 48, s[6])
		self.assertCellChar(0, 56, s[7])
		self.assertCellChar(0, 64, s[8])
		self.assertCellChar(0, 65, '\t')
		self.assertCellChar(0, 66, s[9])
		self.assertCellChar(0, 67, '\t')
		self.assertCellChar(0, 68, s[10])
		self.assertCellChar(0, 69, '\t')
		self.assertCellChar(0, 70, s[11])
		self.assertCellChar(0, 71, s[19])

	def test_noAutowrap(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for i in range(self.vty.cols):
			self.vty.interpret(s[i % len(s)])

		self.vty.interpret('1')
		self.vty.interpret('2')
		self.vty.interpret('3')

		self.vty.interpret(chr(0x1d))
		self.vty.interpret('\n')
		self.vty.interpret('9')

		for i in range(self.vty.cols):
			if i == self.vty.cols - 1:
				c = '3'
			else:
				c = s[i % len(s)]
			self.assertCellChar(0, i, c)

		self.assertCellChar(1, 0, '9')

	def test_eraseLine(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for line in range(2):
			for i in range(self.vty.cols):
				self.vty.interpret(s[i % len(s)])
			self.vty.interpret('\r')
			self.vty.interpret('\n')

		# Move cursor to row 0 col 47
		self.vty.interpret(chr(0x1d))
		for i in range(47):
			self.vty.interpret(chr(0x18))
		self.vty.interpret(chr(0x1e))

		for line in range(2):
			for i in range(self.vty.cols):
				if line == 0 and i >= 47:
					c = ''
				else:
					c = s[i % len(s)]

				self.assertCellChar(line, i, c)

	def test_eraseScreen(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for line in range(15):
			for i in range(self.vty.cols):
				self.vty.interpret(s[i % len(s)])
			self.vty.interpret('\r')
			self.vty.interpret('\n')

		# Move cursor to row 6 col 47
		self.vty.interpret(chr(0x1d))
		for i in range(47):
			self.vty.interpret(chr(0x18))
		for i in range(6):
			self.vty.interpret(chr(0x0b))

		self.vty.interpret(chr(0x1f))

		for line in range(15):
			for i in range(self.vty.cols):
				if line == 6 and i >= 47:
					c = ''
				elif line > 6:
					c = ''
				else:
					c = s[i % len(s)]

				self.assertCellChar(line, i, c)

	def test_cursorAddressing(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for line in range(15):
			for i in range(self.vty.cols):
				self.vty.interpret(s[i % len(s)])
			self.vty.interpret('\r')
			self.vty.interpret('\n')

		# Content Address to row 5 col 4
		self.vty.interpret(chr(0x0e))
		self.vty.interpret('%')
		self.vty.interpret('$')

		self.vty.interpret('1')
		self.vty.interpret('1')
		self.vty.interpret('1')
		self.vty.interpret('1')
		self.vty.interpret('1')

		for line in range(15):
			for i in range(self.vty.cols):
				if line == 5 and i >= 4 and i <= 8:
					c = '1'
				else:
					c = s[i % len(s)]

				self.assertCellChar(line, i, c)

class VT100Tests(TerminalTestCase):
	'''Test the VT100 class'''
	def setUp1(self):
		self.vty = lousy.VT100()

	def tearDown1(self):
		pass

	def sendEsc(self, string):
		self.vty.interpret(chr(0x1b))
		for c in string:
			self.vty.interpret(c)

	def placeCursor(self, row, col):
		self.sendEsc('[%d;%df' % (row + 1, col + 1))

	def test_clearScreen_toEnd_default(self):
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')
		self.vty.interpret('\r')
		self.vty.interpret('\n')
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')

		self.vty.current_row = 0
		self.vty.current_col = 5
		self.sendEsc('[J')

		for i in range(self.vty.cols - 2):
			if i < 5:
				c = 'a'
			else:
				c = ''
			self.assertCellChar(0, i, c)
		for i in range(self.vty.cols - 2):
			self.assertCellChar(1, i, '')

	def test_clearScreen_toEnd(self):
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')
		self.vty.interpret('\r')
		self.vty.interpret('\n')
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')

		self.vty.current_row = 0
		self.vty.current_col = 5
		self.sendEsc('[0J')

		for i in range(self.vty.cols - 2):
			if i < 5:
				c = 'a'
			else:
				c = ''
			self.assertCellChar(0, i, c)
		for i in range(self.vty.cols - 2):
			self.assertCellChar(1, i, '')

	def test_clearScreen_fromStart(self):
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')
		self.vty.interpret('\r')
		self.vty.interpret('\n')
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')

		self.vty.current_row = 1
		self.vty.current_col = 5
		self.sendEsc('[1J')

		for i in range(self.vty.cols - 2):
			self.assertCellChar(0, i, '')
		for i in range(self.vty.cols - 2):
			if i > 5:
				c = 'a'
			else:
				c = ''
			self.assertCellChar(1, i, c)

	def test_clearScreen_all(self):
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')
		self.vty.interpret('\r')
		self.vty.interpret('\n')
		for i in range(self.vty.cols - 2):
			self.vty.interpret('a')

		self.sendEsc('[2J')

		for i in range(self.vty.cols - 2):
			self.assertCellChar(0, i, '')
		for i in range(self.vty.cols - 2):
			self.assertCellChar(1, i, '')

	def test_argumentlessCursorPlace(self):
		for i in range(self.vty.rows - 2):
			self.vty.interpret('a')
			self.vty.interpret('\n')

		self.vty.interpret(chr(0x1b))
		self.vty.interpret('[')
		self.vty.interpret('f')
		
		self.vty.interpret('b')

		self.assertCellChar(0, 0, 'b')
		for i in range(1, self.vty.rows - 2):
			self.assertCellChar(i, i, 'a')

	def test_emptyArgumentCursorPlace(self):
		for i in range(self.vty.rows - 2):
			self.vty.interpret('a')
			self.vty.interpret('\n')

		self.vty.interpret(chr(0x1b))
		self.vty.interpret('[')
		self.vty.interpret(';')
		self.vty.interpret('f')
		
		self.vty.interpret('b')

		self.assertCellChar(0, 0, 'b')
		for i in range(1, self.vty.rows - 2):
			self.assertCellChar(i, i, 'a')

	def test_argumentCursorPlace(self):
		for i in range(self.vty.rows - 2):
			self.vty.interpret('a')
			self.vty.interpret('\n')

		self.vty.interpret(chr(0x1b))
		self.vty.interpret('[')
		self.vty.interpret('2')
		self.vty.interpret('0')
		self.vty.interpret(';')
		self.vty.interpret('2')
		self.vty.interpret('0')
		self.vty.interpret('f')
		
		self.vty.interpret('b')

		# cells are 1-indexed in the spec
		self.assertCellChar(19, 19, 'b')
		for i in range(self.vty.rows - 2):
			if i != 19:
				self.assertCellChar(i, i, 'a')

	def test_moveCursorBackwards_default(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.assertEqual(self.vty.current_col, 79)

		self.sendEsc('[D')
		self.sendEsc('[D')
		self.sendEsc('[D')

		self.assertEqual(self.vty.current_col, 76)

		self.vty.interpret('b')

		self.assertCellChar(0, 75, 'a')
		self.assertCellChar(0, 76, 'b')
		self.assertCellChar(0, 77, 'a')

	def test_moveCursorBackwards_one(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.assertEqual(self.vty.current_col, 79)

		self.sendEsc('[1D')
		self.sendEsc('[1D')
		self.sendEsc('[1D')

		self.assertEqual(self.vty.current_col, 76)

		self.vty.interpret('b')

		self.assertCellChar(0, 75, 'a')
		self.assertCellChar(0, 76, 'b')
		self.assertCellChar(0, 77, 'a')

	def test_moveCursorBackwards_zero(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.assertEqual(self.vty.current_col, 79)

		self.sendEsc('[0D')
		self.sendEsc('[0D')
		self.sendEsc('[0D')

		self.assertEqual(self.vty.current_col, 76)

		self.vty.interpret('b')

		self.assertCellChar(0, 75, 'a')
		self.assertCellChar(0, 76, 'b')
		self.assertCellChar(0, 77, 'a')

	def test_moveCursorBackwards_arg(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.assertEqual(self.vty.current_col, 79)

		self.sendEsc('[3D')

		self.assertEqual(self.vty.current_col, 76)

		self.vty.interpret('b')

		self.assertCellChar(0, 75, 'a')
		self.assertCellChar(0, 76, 'b')
		self.assertCellChar(0, 77, 'a')

	def test_moveCursorBackwards_leftPastMargin(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.assertEqual(self.vty.current_col, 79)

		self.sendEsc('[300D')

		self.assertEqual(self.vty.current_col, 0)

		self.vty.interpret('b')

		self.assertCellChar(0, 0, 'b')
		self.assertCellChar(0, 1, 'a')

	def test_moveCursorForwards_default(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.placeCursor(0, 0)
		self.assertEqual(self.vty.current_col, 0)

		self.sendEsc('[C')
		self.sendEsc('[C')
		self.sendEsc('[C')

		self.assertEqual(self.vty.current_col, 3)

		self.vty.interpret('b')

		self.assertCellChar(0, 2, 'a')
		self.assertCellChar(0, 3, 'b')
		self.assertCellChar(0, 4, 'a')

	def test_moveCursorForwards_one(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.placeCursor(0, 0)
		self.assertEqual(self.vty.current_col, 0)

		self.sendEsc('[1C')
		self.sendEsc('[1C')
		self.sendEsc('[1C')

		self.assertEqual(self.vty.current_col, 3)

		self.vty.interpret('b')

		self.assertCellChar(0, 2, 'a')
		self.assertCellChar(0, 3, 'b')
		self.assertCellChar(0, 4, 'a')

	def test_moveCursorForwards_zero(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.placeCursor(0, 0)
		self.assertEqual(self.vty.current_col, 0)

		self.sendEsc('[0C')
		self.sendEsc('[0C')
		self.sendEsc('[0C')

		self.assertEqual(self.vty.current_col, 3)

		self.vty.interpret('b')

		self.assertCellChar(0, 2, 'a')
		self.assertCellChar(0, 3, 'b')
		self.assertCellChar(0, 4, 'a')

	def test_moveCursorForwards_arg(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.placeCursor(0, 0)
		self.assertEqual(self.vty.current_col, 0)

		self.sendEsc('[3C')

		self.assertEqual(self.vty.current_col, 3)

		self.vty.interpret('b')

		self.assertCellChar(0, 2, 'a')
		self.assertCellChar(0, 3, 'b')
		self.assertCellChar(0, 4, 'a')

	def test_moveCursorForwards_rightPastMargin(self):
		for i in range(self.vty.cols - 1):
			self.vty.interpret('a')

		self.placeCursor(0, 0)
		self.assertEqual(self.vty.current_col, 0)

		self.sendEsc('[300C')

		self.assertEqual(self.vty.current_col, 79)

		self.vty.interpret('b')

		self.assertCellChar(0, 78, 'a')
		self.assertCellChar(0, 79, 'b')

	def test_moveCursorUp_default(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.sendEsc('[1D')

		self.assertEqual(self.vty.current_row, 23)

		self.sendEsc('[A')
		self.sendEsc('[A')
		self.sendEsc('[A')

		self.assertEqual(self.vty.current_row, 20)

		self.vty.interpret('b')

		self.assertCellChar(19, 20, 'a')
		self.assertCellChar(20, 20, 'b')
		self.assertCellChar(21, 20, 'a')

	def test_moveCursorUp_one(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.sendEsc('[1D')

		self.assertEqual(self.vty.current_row, 23)

		self.sendEsc('[1A')
		self.sendEsc('[1A')
		self.sendEsc('[1A')

		self.assertEqual(self.vty.current_row, 20)

		self.vty.interpret('b')

		self.assertCellChar(19, 20, 'a')
		self.assertCellChar(20, 20, 'b')
		self.assertCellChar(21, 20, 'a')

	def test_moveCursorUp_zero(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.sendEsc('[1D')

		self.assertEqual(self.vty.current_row, 23)

		self.sendEsc('[0A')
		self.sendEsc('[0A')
		self.sendEsc('[0A')

		self.assertEqual(self.vty.current_row, 20)

		self.vty.interpret('b')

		self.assertCellChar(19, 20, 'a')
		self.assertCellChar(20, 20, 'b')
		self.assertCellChar(21, 20, 'a')

	def test_moveCursorUp_arg(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.sendEsc('[1D')

		self.assertEqual(self.vty.current_row, 23)

		self.sendEsc('[3A')

		self.assertEqual(self.vty.current_row, 20)

		self.vty.interpret('b')

		self.assertCellChar(19, 20, 'a')
		self.assertCellChar(20, 20, 'b')
		self.assertCellChar(21, 20, 'a')

	def test_moveCursorUp_upPastMargin(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.sendEsc('[1D')

		self.assertEqual(self.vty.current_row, 23)

		self.sendEsc('[300A')

		self.assertEqual(self.vty.current_row, 0)

		self.vty.interpret('b')

		self.assertCellChar(0, 20, 'b')
		self.assertCellChar(1, 20, 'a')

	def test_moveCursorDown_default(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.placeCursor(0, 20)

		self.assertEqual(self.vty.current_row, 0)

		self.sendEsc('[B')
		self.sendEsc('[B')
		self.sendEsc('[B')

		self.assertEqual(self.vty.current_row, 3)

		self.vty.interpret('b')

		self.assertCellChar(2, 20, 'a')
		self.assertCellChar(3, 20, 'b')
		self.assertCellChar(4, 20, 'a')

	def test_moveCursorDown_one(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.placeCursor(0, 20)

		self.assertEqual(self.vty.current_row, 0)

		self.sendEsc('[1B')
		self.sendEsc('[1B')
		self.sendEsc('[1B')

		self.assertEqual(self.vty.current_row, 3)

		self.vty.interpret('b')

		self.assertCellChar(2, 20, 'a')
		self.assertCellChar(3, 20, 'b')
		self.assertCellChar(4, 20, 'a')

	def test_moveCursorDown_zero(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.placeCursor(0, 20)

		self.assertEqual(self.vty.current_row, 0)

		self.sendEsc('[0B')
		self.sendEsc('[0B')
		self.sendEsc('[0B')

		self.assertEqual(self.vty.current_row, 3)

		self.vty.interpret('b')

		self.assertCellChar(2, 20, 'a')
		self.assertCellChar(3, 20, 'b')
		self.assertCellChar(4, 20, 'a')

	def test_moveCursorDown_arg(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.placeCursor(0, 20)

		self.assertEqual(self.vty.current_row, 0)

		self.sendEsc('[3B')

		self.assertEqual(self.vty.current_row, 3)

		self.vty.interpret('b')

		self.assertCellChar(2, 20, 'a')
		self.assertCellChar(3, 20, 'b')
		self.assertCellChar(4, 20, 'a')

	def test_moveCursorDown_downPastMargin(self):
		self.placeCursor(0, 21)
		for i in range(self.vty.rows - 1):
			self.sendEsc('[1D')
			self.vty.interpret('a')
			self.vty.interpret('\n')
		self.placeCursor(0, 20)

		self.assertEqual(self.vty.current_row, 0)

		self.sendEsc('[300B')

		self.assertEqual(self.vty.current_row, 23)

		self.vty.interpret('b')

		self.assertCellChar(22, 20, 'a')
		self.assertCellChar(23, 20, 'b')

class VttyTests(TerminalTestCase):
	'''Test the Vtty class'''
	def setUp1(self):
		self.vtty = lousy.Vtty('dumb')

	def tearDown1(self):
		pass

	def test_string(self):
		s = 'abcdefghijklmnopqrstuvwxyz'

		for i in range(4):
			self.vtty.append(s)

		t = self.vtty.string(0, 0, len(s))
		self.assertEqual(t, s)

		t = self.vtty.string(0, 10, len(s) - 10)
		self.assertEqual(t, s[10:])

		t = self.vtty.string(0, 79, 30)
		self.assertEqual(t, self.vtty.cell(0, 79).char)

