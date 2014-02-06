# Tests of the Stub Protocol

import lousy
import socket
import struct
import threading

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

	def createStub(self, classname):
		port = lousy.stubs.port()
		sock = socket.create_connection(('localhost', port))

		send(sock, '%s,id1' % classname)

		return sock

	def test_connectStubNoInit(self):
		port = lousy.stubs.port()
		sock = socket.create_connection(('localhost', port))
		sock.close()

	def test_connectSimpleStub(self):
		sock = self.createStub('SimpleStub')

	def callback_SimpleStub(self, stub, type):
		self.stub = stub
		self.type = type
		self.ready.set()

	def test_defaultStubCallback(self):
		self.ready = threading.Event()
		self.stub = None
		self.type = ''

		lousy.stubs.add_class('default', None, self.callback_SimpleStub)

		sock = self.createStub('SimpleStub')

		self.ready.wait(5)

		self.assertIsNotNone(self.stub)
		self.assertEqual(self.type, 'SimpleStub')

		sock.close()

	def test_nonExistentStubCallback(self):
		self.ready = threading.Event()
		self.stub = None
		self.type = ''

		lousy.stubs.add_class('default', None, self.callback_SimpleStub)

		sock = self.createStub('StubClassWhichDoesntExist')

		self.ready.wait(5)

		self.assertIsNotNone(self.stub)
		self.assertEqual(self.type, 'SimpleStub')

		sock.close()

	def test_waitForStub(self):
		sock = self.createStub('SimpleStub')

		stub = lousy.stubs.waitForStub()

		self.assertIsNotNone(stub)
		self.assertEqual(stub.type, 'SimpleStub')

	def test_waitForStubWithType(self):
		sock = self.createStub('SimpleStub')

		stub = lousy.stubs.waitForStub('SimpleStub')

		self.assertIsNotNone(stub)
		self.assertEqual(stub.type, 'SimpleStub')

	def test_waitForStubWithInvalidType(self):
		sock = self.createStub('SimpleStub')

		stub = lousy.stubs.waitForStub('NotSoSimpleStub', timeout=0.1)

		self.assertIsNone(stub)

class SimpleStubTests(StubTestCase):
	def setUp1(self):
		port = lousy.stubs.port()
		self.sock = socket.create_connection(('localhost', port))

		send(self.sock, 'SimpleStub,id1')

		self.stub = lousy.stubs.waitForStub()

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
		s = 'This is a write test'
		self.send(s)

		t = self.stub.read()
		self.assertEqual(s, t)

	def test_readFromStub(self):
		s = 'This is a read test'
		self.stub.write(s)

		t = self.recv()
		self.assertEqual(s, t)
