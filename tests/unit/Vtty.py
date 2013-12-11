# Tests of the various emulated terminal classes

import lousy

class TerminalTestCase(lousy.TestCase):
	def assertCellChar(self, cell, char):
		self.assertIsNotNone(cell)
		self.assertEqual(cell.char, char)

class EmulatedTerminalTests(TerminalTestCase):
	''' Test the EmulatedTerminal class '''
	def setUp1(self):
		self.vty = lousy.EmulatedTerminal()

	def tearDown1(self):
		pass

	def test_basicEcho(self):
		self.vty.interpret('a')
		cell = self.vty.cell(0, 0)
		self.assertCellChar(cell, 'a')

		self.vty.interpret('s')
		cell = self.vty.cell(0, 1)
		self.assertCellChar(cell, 's')

		self.vty.interpret('d')
		cell = self.vty.cell(0, 2)
		self.assertCellChar(cell, 'd')

		self.vty.interpret('f')
		cell = self.vty.cell(0, 3)
		self.assertCellChar(cell, 'f')

	def test_echoWrapAround(self):
		for i in range(self.vty.cols):
			self.vty.interpret('a')

		cell = self.vty.cell(1, 0)
		self.assertCellChar(cell, '')

		self.vty.interpret('b')
		cell = self.vty.cell(1, 0)
		self.assertCellChar(cell, 'b')
