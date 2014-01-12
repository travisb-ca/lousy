# Tests of the Stub Protocol

import lousy

class StubTestCase(lousy.TestCase):
	pass

class StubCentralTests(StubTestCase):
	def test_testCanAccessStubCentral(self):
		self.assertIsNotNone(lousy.stubs)

	def test_stubCentralGetsReady(self):
		self.assertIsNotNone(lousy.stubs.port())
