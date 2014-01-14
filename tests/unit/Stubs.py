# Tests of the Stub Protocol

import lousy
import socket
import struct

def send(sock, msg):
	'''Send the given message to the stub as the far end
	'''
	buf = struct.pack(lousy.MSG_HEADER_FMT, len(msg))
	return sock.send(buf + msg)

class StubTestCase(lousy.TestCase):
	pass

class StubCentralTests(StubTestCase):
	def test_testCanAccessStubCentral(self):
		self.assertIsNotNone(lousy.stubs)

	def test_stubCentralGetsReady(self):
		self.assertIsNotNone(lousy.stubs.port())

	def test_connectStubNoInit(self):
		port = lousy.stubs.port()
		sock = socket.create_connection(('localhost', port))
		sock.close()

	def test_connectSimpleStub(self):
		port = lousy.stubs.port()
		sock = socket.create_connection(('localhost', port))

		send(sock, 'SimpleStub,id1')
