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

class SimpleStubTests(StubTestCase):
	def setUp1(self):
		port = lousy.stubs.port()
		self.sock = socket.create_connection(('localhost', port))

		send(self.sock, 'SimpleStub,id1')

		self.stub = lousy.stubs.newest()
		while self.stub is None:
			self.stub = lousy.stubs.newest()

	def tearDown1(self):
		if self.sock:
			self.sock.close()

	def send(self, msg):
		send(self.sock, msg)

	def recv(self):
		'''Get the latest messge from the stub and return it as a string
		'''
		size = self.sock.recv(4)
		size = struct.unpack(lousy.MSG_HEADER_FMT, size)[0]

		buf = self.sock.recv(size)

		return buf

	def test_writeToStub(self):
		s = 'This is a test'
		self.send(s)

		t = self.stub.read()
		self.assertEqual(s, t)

	def test_readFromStub(self):
		s = 'This is a test'
		self.stub.write(s)

		t = self.recv()
		self.assertEqual(s, t)
