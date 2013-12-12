# Tests of the various emulated terminal classes

import lousy

class TerminalTestCase(lousy.TestCase):
	def assertCellChar(self, row, col, char):
		cell = self.vty.cell(row, col)
		self.assertIsNotNone(cell)
		self.assertEqual(cell.char, char)

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
