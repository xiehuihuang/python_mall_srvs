#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: inventory.py
# @time: 2021-10-30 22:34
# @author: jack
# @Email:793936517@qq.com
# @desc:

import json
import grpc
import consul

from google.protobuf import empty_pb2

from inventory_srv.proto import inventory_pb2, inventory_pb2_grpc
from inventory_srv.settings import settings


class InventoryTest:
    def __init__(self):
        #连接grpc服务器
        c = consul.Consul(host="192.168.0.104", port=8500)
        services = c.agent.services()
        ip = ""
        port = ""
        for key, value in services.items():
            if value["Service"] == settings.SERVICE_NAME:
                ip = value["Address"]
                port = value["Port"]
                break
        if not ip:
            raise Exception()
        channel = grpc.insecure_channel(f"{ip}:{port}")
        self.inventory_stub = inventory_pb2_grpc.InventoryStub(channel)

    def set_inv(self):
        rsp = self.inventory_stub.SetInv(
            inventory_pb2.GoodsInvInfo(goodsId=10, num=110)
        )

    def get_inv(self):
        rsp = self.inventory_stub.InvDetail(
            inventory_pb2.GoodsInvInfo(goodsId=3)
        )
        print(rsp.num)

    def sell(self):
        goods_list = [(1,3), (3, 5)]
        request = inventory_pb2.SellInfo()
        for goodsId, num in goods_list:
            request.goodsInfo.append(inventory_pb2.GoodsInvInfo(goodsId=goodsId, num=num))
        rsp = self.inventory_stub.Sell(request)

    def reback(self):
        goods_list = [(1, 3), (30, 5)]
        request = inventory_pb2.SellInfo()
        for goodsId, num in goods_list:
            request.goodsInfo.append(inventory_pb2.GoodsInvInfo(goodsId=goodsId, num=num))
        rsp = self.inventory_stub.Reback(request)


if __name__ == "__main__":
    inv = InventoryTest()
    # goods.goods_list()

    # goods.batch_get()
    # goods.get_detail(421)
    # inv.set_inv()
    # inv.get_inv()
    inv.sell()
    # inv.reback()
