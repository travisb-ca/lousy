# Tests of the Stub Protocol

import lousy
import socket
import struct

class StubTestCase(lousy.TestCase):
	def send(self, sock, msg):
		'''Send the given message to the stub as the far end
		'''
		buf = struct.pack(lousy.MSG_HEADER_FMT, len(msg))
		return sock.send(buf + msg)

class StubCentralTests(StubTestCase):
	def test_testCanAccessStubCentral(self):
		self.assertIsNotNone(lousy.stubs)

	def test_stubCentralGetsReady(self):
		self.assertIsNotNone(lousy.stubs.port())

	def test_connectSimpleStub(self):
		port = lousy.stubs.port()
		sock = socket.create_connection(('localhost', port))
		sock.close()
