# Pascl-Server
一个很简单——真的很简单的HTTP服务端

# 注意
本项目目前仅支持以下METHOD

+ POST
+ GET
+ DELETE
+ PUT
+ OPTIONS
+ HEAD

支持绑定事件的只有以下METHOD

+ POST
+ GET
+ OPTIONS

但该项目仍在持续完善中！

# 食用
本体只有一个Python文件```pascl_server.py```，下载后置于项目中

``` python
from pascl_server import CreateServer
```

以此调用pascl_server

**pascl_server下有很多函数、方法，但只有CreateServer可以直接调用！**

然后就可以创建、启动服务端了

``` python
server = CreateServer()

// code...

server.listen(3000)
```

# API
## server.listen(port)
服务器监听端口

关于这个```port```我是这么处理的

``` python
temp = str(port).split(":")
if len(temp) == 1:
  ip = "0.0.0.0"
  port = int("".join(temp))
else:
  ip = ":".join(temp[:-1])
  port = int(temp[-1])

  if ip.rstrip() == "":
    ip = "0.0.0.0"
```

从代码可以看出来，port可以如下写

+ 3000（Open at 0.0.0.0:3000）
+ :3000（= 3000）
+ 127.0.0.1:3000
+ [fe80::f5cc:bfcd:c76e:17b]:3000（Support IPv6！）

该函数是一个死循环函数

但得益于内部使用的多线程库为```threading```，你可以让该函数在另一个线程运行

## server.get|post|options(path,require)
绑定对应的METHOD

### path
绑定路径
该参数在存储前会经过如下处理

``` python
'^{}$'.format(path)
```

没错，该参数可以是正则表达式，并且不能加上头尾的```^```和```$```

### require
回调函数

会给函数三个参数request、response、next

request为处理后的客户端信息

response为服务端返回操作（详细请看require.response条目）

next为一个函数，如果不执行会导致加入时间比自己晚的路由无法执行，但不会让程序出错

看到这里大概明白了吧，本项目是对照```express```开发的

## server.all()
参数、介绍大致同上

但该函数绑定了所有METHOD！

## require.response
有许多方法

### pipe()
该函数运行后，允许输出无穷无尽的流数据，并在运行```response.end```后强制结束

进而言之就是可以一直输出数据，并且客户端还有反应啦

再详细一点就是——返回不需要```content-type```文件头？

### write(buf)
buf仅能为bytes类型

该函数会把内容输入缓存区，并在执行```response.end```后一次性返回给客户端

就是HTTP协议中的body部分的输出啦

### end([buf])
运行该函数后，服务器会返回所有信息

简单来说就是运行了这个，客户端就会收到完整的HTTP协议啦

### http_status(code,[msg])
设置HTTP状态，比如200

code 为状态码
msg 则为详细状态

比如 404 Not Found ，code 为 404，msg 为 Not Found

### setHeader(name, value)
设置头（HEADER）

### setHeader(json)
设置多个头

参数例子

``` json
{
  "content-type": "text/html; charset=UTF-8",
  "content-length": 128,
  // ...
}
```
