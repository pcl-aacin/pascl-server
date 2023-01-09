import socket
import urllib.parse
import time
import threading
import queue
import random
import io
import platform
import re
import json

ACTIVE_HTTP_METHODS = [ "GET","POST","HEAD","OPTIONS","PUT","DELETE" ]
ACTIVE_HTTP_VERSIONS = [ 1.0,1.1,2.0 ]

__ROUTER__ = []

# 接收数据的线程
class RecvThread(threading.Thread):
	def __init__(self,client,parent):
		threading.Thread.__init__(self)
		self.client = client
		self.parent = parent

	def run(self):
		client = self.client
		while True:
			try:
				data = client.recv(1024)
			except Exception as error:
				if client.fileno() == -1:
					break
				else:
					print(error)
			else:
				self.parent.recv.put(data)
			finally:
				if len(data) <= 0:
					self.parent.handleEnd = False
					continue

# 处理数据的线程
class HandleThread(threading.Thread):
	def __init__(self,client,parent):
		threading.Thread.__init__(self)
		self.client = client
		self.parent = parent

	def run(self):
		client = self.client

		handle_header_temp = queue.Queue()
		handle_status = "http_connect"
		self.parent.request = {}
		while True:
			if client.fileno() == -1:
				break

			if not self.parent.recv.empty():
				data = self.parent.recv.get()

				allline = data.split(b"\n")

				try:
					index = 0
					for oneline in allline:
						index += 1

						# 判断 handle_status
						temp = oneline.split(b" ")
						if len(temp) == 3:
							method, fullpath, http_version = temp

							if method.decode().upper() in ACTIVE_HTTP_METHODS:
								handle_status = "http_connect"
								self.parent.handle = None

						if handle_status == "http_connect":
							record = oneline.decode()

							self.parent.request = {}

							# 类似：GET / HTTP/2.0
							temp = record.split(" ")
							method, fullpath, http_version = temp

							if not method.upper() in ACTIVE_HTTP_METHODS:
								# METHOD 不支持或不合法
								raise Exception("not a valid or support http method")

							self.parent.request["method"] = method.lower()
							
							http_version_code = float(http_version.split("/")[-1])
							if not http_version_code in ACTIVE_HTTP_VERSIONS:
								# HTTP_VERSION 不支持或不合法
								raise Exception("not a valid or support http version")

							self.parent.request["http_version"] = http_version_code
							
							temp = fullpath.split("?")
							# 防止 /xxx???a=1
							path = "".join(temp[:1])
							getdatas = "?".join(temp[1:])

							# 路径
							self.parent.request["path"] = path

							query = {}

							for getdata in getdatas.split("&"):
								# 防止 /xxx?a=b&&&v=c
								if getdata.rstrip() == "":
									continue
								
								# 防止 /xxx?a===b
								temp = getdata.split("=")
								name = urllib.parse.unquote("".join(temp[:1]))
								value = urllib.parse.unquote("=".join(temp[1:]))

								query[name] = value

							# GET参数
							self.parent.request["query"] = query

							# HEADER
							self.parent.request["__headers__"] = []

							handle_status = "header"
						elif handle_status == "header":
							record = oneline.decode()

							def resolveHeader(header):
								self.parent.request["__headers__"].append(header)
							
							# 为空
							if record.rstrip() == "":
								if not handle_header_temp.empty():
									resolveHeader(handle_header_temp.get())
								
								handle_status = "body"
								continue

							# 第一个元素
							if index == 1:
								if not handle_header_temp.empty():
									record = handle_header_temp.get() + record
								
								resolveHeader(record)
								continue

							# 最后一个元素
							if index == len(allline):
								handle_header_temp.put(record)
								continue
						
							resolveHeader(record)
						elif handle_status == "body":
							if self.parent.handle == None:
								self.parent.handle = b""
							
							self.parent.handle += oneline

				except Exception as error:
					print(error)

# 返回数据的线程
class ReturnThread(threading.Thread):
	def __init__(self,client,parent):
		threading.Thread.__init__(self)
		self.client = client
		self.parent = parent

	def run(self):
		client = self.client
		router = False

		while True:
			if self.parent.handle == None:
				router = False
			elif router == False:
				router = True
				request = self.parent.request

				request["headers"] = {}
				for header in request["__headers__"]:
					name, value = header.rstrip().split(": ")

					name = name.lower()

					if name == "content-type":
						temp = value.split(";")

						request["content-type"] = temp[0].rstrip()

						for kv in temp[1:]:
							kv = kv.rstrip()
							if kv[:7] == "charset":
								request["charset"] = "=".join(kv.split("=")[1:])

					request["headers"][name] = value


				if request["method"] == "post":
					request["post"] = {}

					while not self.parent.handleEnd:
						pass
					
					data = self.parent.handle.decode().rstrip()

					if data != "":
						if request["content-type"] == "application/x-www-form-urlencoded":
							for postdata in data.split("&"):
								# 防止 a=b&&&v=c
								if postdata.rstrip() == "":
									continue
								
								# 防止 a===b
								temp = postdata.split("=")
								name = urllib.parse.unquote("".join(temp[:1]))
								value = urllib.parse.unquote("=".join(temp[1:]))

								request["post"][name] = value
						elif request["content-type"] == "application/json":
							try:
								request["post"] = json.loads(data)
							except:
								pass

				class CreateResponse:
					def __init__(self):
						self.connectStatus = "http_status"
						self.http_status = { "code": 200, "msg": "" }
						self.header = {
							"server": 'PasclServer/Beta Python/'.format(platform.python_version()).encode()
						}
						self.body = b""
					
					def http_status(self,code,msg):
						if connectStatus == "body":
							raise Exception("You can not output http_status after output body")
							return

						self.http_status["code"] = code
						self.http_status["msg"] = msg
					
					def setHeader(self,name,value):
						if self.connectStatus == "body":
							raise Exception("You can not output header after output body")
							return

						self.header[name] = value
					def setHeaders(self,json):
						for name, value in json.items():
							self.setHeader(name.lower(),value)
					
					def write(self,buf):
						if self.connectStatus == "http_status" or self.connectStatus == "header":
							client.send('HTTP/1.1 {} {}'.format(self.http_status["code"],self.http_status["msg"]).encode())
							client.send(b'\r\n')

							for name, value in self.header.items():
								client.send('{}: {}'.format(name,value).encode())
								client.send(b'\r\n')
							
							self.connectStatus = "body"
						
						if type(self.body) != None:
							self.body += buf
					
					def end(self,buf = b""):
						self.write(buf)
						if self.body != None:
							body = self.body
							self.body = None

							if not "content-length" in self.header:
								client.send('content-length: {}'.format(len(body)).encode())
								client.send(b'\r\n')
							
							client.send(b'\r\n')

							client.send(body)
						else:
							raise Exception("You can not use end again")
					
					def pipe(self):
						client.send(b'\r\n')
						while self.body != None and self.body != b"":
							client.send(self.body)
							self.body = b""
				
				response = CreateResponse()

				canNext = False
				hasRouter = False
				def next():
					canNext = True
					
				for router in __ROUTER__:
					if re.match(router["path"], request["path"]) == None:
						continue
					
					if re.match(router["method"].lower(), request["method"].lower()) == None:
						continue
						
					hasRouter = True
					router["require"](request,response,next)

					if not canNext:
						break
				
				if not hasRouter:
					response.setHeader("content-type", "text/html; chatset=UTF-8")
					response.end("Can not get {}".format(request["path"]).encode())
				break


class NewConnection(threading.Thread):
	def __init__(self,pid,client):
		threading.Thread.__init__(self)
		self.pid = pid
		self.client = client
		self.child_threads = queue.Queue()
	
	def run(self):
		client = self.client
		self.recv = queue.Queue()
		self.handle = None
		self.handleEnd = True

		# 接收数据的线程
		recv_thread = RecvThread(client,self)
		recv_thread.start()
		self.child_threads.put(recv_thread)

		# 处理数据的线程
		handle_thread = HandleThread(client,self)
		handle_thread.start()
		self.child_threads.put(handle_thread)

		# 返回数据的线程
		return_thread = ReturnThread(client,self)
		return_thread.start()
		self.child_threads.put(return_thread)

class CreateServer:
	def __init__(self):
		self.server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

		self.threads = queue.Queue()
		self.threadId = 0

		self.config = {
			"maxConnection": 100
		}
	
	def listen(self,port,**kv):
		temp = str(port).split(":")
		if len(temp) == 1:
			ip = "0.0.0.0"
			port = int("".join(temp))
		else:
			ip = ":".join(temp[:-1])
			port = int(temp[-1])

			if ip.rstrip() == "":
				ip = "0.0.0.0"
		
		self.server.bind((ip,port))

		self.server.listen(self.config["maxConnection"])

		while True:
			client, address = self.server.accept()

			# 为连接开启新线程
			thread = NewConnection(self.threadId,client)
			thread.start()
			self.threads.put(thread)

			self.threadId += 1
	
	def options(self,path,require = False):
		return self.__regrouter__(path, require, r"options")
	def get(self,path,require = False):
		return self.__regrouter__(path, require, r"get")
	def post(self,path,require = False):
		return self.__regrouter__(path, require, r"post")
	def all(self,path,require = False):
		return self.__regrouter__(path, require, r".*")
		
	def __regrouter__(self,path,require,method):
		def fn(require):
			__ROUTER__.append({
				"path": '^{}$'.format(path),
				"require": require,
				"method": method
			})

		if require == False:
			return fn
		else:
			fn(require)