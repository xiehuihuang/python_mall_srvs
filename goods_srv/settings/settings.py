#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: settings.py
# @time: 2022-10-24 20:58
# @author: jack
# @Email:793936517@qq.com
# @desc:


import json

import nacos
from playhouse.pool import PooledMySQLDatabase
from playhouse.shortcuts import ReconnectMixin
from loguru import logger


# 使用peewee的连接池， 使用ReconnectMixin来防止出现连接断开查询失败
class ReconnectMysqlDatabase(ReconnectMixin, PooledMySQLDatabase):
    pass


NACOS = {
    "Host": "127.0.0.1",
    "Port": 8848,
    "NameSpace": "7bc0b61a-4547-4a93-ba24-299947e7a7f8",
    "User": "nacos",
    "Password": "nacos",
    "DataId": "goods_srv.json",
    "Group": "dev"
}

client = nacos.NacosClient(f'{NACOS["Host"]}:{NACOS["Port"]}', namespace=NACOS["NameSpace"],
                           username=NACOS["User"],
                           password=NACOS["Password"])

# get config
data = client.get_config(NACOS["DataId"], NACOS["Group"])
data = json.loads(data)
logger.info(data)


def update_cfg(args):
    print("配置产生变化")
    print(args)

# consul的配置
CONSUL_HOST = data["consul"]["host"]
CONSUL_PORT = data["consul"]["port"]

# 服务相关的配置
SERVICE_NAME = data["name"]
SERVICE_TAGS = data["tags"]

DB = ReconnectMysqlDatabase(data["mysql"]["db"], host=data["mysql"]["host"], port=data["mysql"]["port"],
                            user=data["mysql"]["user"], password=data["mysql"]["password"])