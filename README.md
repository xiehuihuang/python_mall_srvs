# python_mall_srvs
电商系统-微服务python_mall_srvs 

#### 一、开发环境安装：
1.1 项目开发工具及使用技术栈
  + python: 3.8.10
  + 开发工具：pyCharm2021.1.3
  + 技术栈 python、orm、protobuf/grpc、consul、nacos、docker
  + 数据库：mysql8、redis5.0

1.2 代码git clone
  + git clone仓库代码：git clone git@github.com:xiehuihuang/python_mall_srvs.git
  + go mod tidy
  
1.3 docker安装mysql
  + 下载镜像：docker pull mysql:8.0.22
  + 查看镜像：docker images
  + 通过镜像启动：
  > ```shell
  > docker run -p 3306:3306 --name mysql -v $PWD/data/developer/mysql/conf:/etc/mysql/conf.d -v  $PWD/data/developer/mysql/logs:/logs -v  $PWD/data/developer/mysql/data:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=123456 -d mysql:8.0.22
  > ```
  + 重启容器：docker restart mysql
  + 查看镜像：docker ps -a
  + 停止正在运行镜像：docker stop mysql
  + 删除镜像：docker rm mysql

1.4 docker安装redis
  + 下载镜像：docker pull redis:latest
  + 查看镜像：docker images
  + 通过镜像启动：
  > ```shell
  > docker run -p 6379:6379 --name redis -d redis:latest --requirepass "123456"
  > ```
  + 重启容器：docker restart redis
  + 查看镜像：docker ps -a 

1.5 docker安装consul服务
  + 拉取镜像：docker pull consul:latest
  + 安装
  > ```shell
  > docker run -d -p 8500:8500 -p 8300:8300 -p 8301:8301 -p 8302:8302 -p 8600:8600/udp consul consul agent -dev -client=0.0.0.0
  > docker container update --restart=always 容器id 
  > ```
  + 浏览器访问：http://127.0.0.1:8500

1.6 docker安装nacos配置中心服务
  + 下载安装
  > ```shell
  > docker run --name nacos-standalone -e MODE=standalone -e JVM_XMS=512m -e JVM_XMX=512m -e JVM_XMN=256m -p 8848:8848 -d nacos/nacos-server:latest
  > ```
  + 访问： http://127.0.0.1:8848/nacos
  + 登录：账号密码都是nacos
  
##### 二、用户微服务（user_srv）：  
1 用户服务 
  + 用户列表
  + 添加用户
  + 更新用户
  + 查询用户——通过id
  + 查询用户——通过mobile 
  + 检查密码
  + user_srv依赖包安装：
  ``` shell
  pip install -r requirement.txt -i https://pypi.douban.com/simple
  ```

2 生成proto的python文件
  + python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. user.proto
  
3 grpc consul服务注册和注销、服务注册健康检查

4 nacos配置服务中心: user_srv.json 配置信息如下
```json
{
    "name": "user_srv",
    "host": "127.0.0.1",
    "tags": ["user_srv", "python-grpc", "srv"],
    "mysql": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "123456",
        "db": "python_user_srv"
    },
    "consul": {
        "host": "127.0.0.1",
        "port": 8500
    }
}
```

##### 三、商品微服务（goods_srv）：  
1 商品服务 
  + 商品模块(商品列表、批量获取商品信息、商品增/删/查/改)
  + 商品分类（获取所有的分类）
  + 商品子分类（获取子分类列表信息、新建、删除、修改分类信息）
  + 商品品牌
  + 商品轮播图（获取轮播图列表信息、添加、删除、修改轮播图）
  + 品牌分类
  + 通过分类获取品牌
  ``` shell
  pip install -r requirement.txt -i https://pypi.douban.com/simple
  ```

2 生成proto的python文件
  + python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. goods.proto
  
3 grpc consul服务注册和注销、服务注册健康检查

4 nacos配置服务中心: user_srv.json 配置信息如下
```json
{
    "name": "goods_srv",
    "host": "127.0.0.1",
    "tags": ["goods_srv", "python-grpc", "srv"],
    "mysql": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "123456",
        "db": "python_goods_srv"
    },
    "consul": {
        "host": "127.0.0.1",
        "port": 8500
    }
}
```
