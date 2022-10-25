#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: server.py
# @time: 2021-10-30 22:14
# @author: jack
# @Email:793936517@qq.com
# @desc:

import sys
import os
import logging
import signal
import argparse
import socket
from concurrent import futures
from functools import partial

import grpc
from loguru import logger
from rocketmq.client import PushConsumer, ConsumeStatus

BASE_DIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, BASE_DIR)

from inventory_srv.proto import inventory_pb2, inventory_pb2_grpc
from inventory_srv.handler.inventory import InventoryServicer, reback_inv
from common.grpc_health.v1 import health_pb2_grpc, health_pb2
from common.grpc_health.v1 import health
from common.register import consul
from inventory_srv.settings import settings


def on_exit(signo, frame, service_id):
    register = consul.ConsulRegister(settings.CONSUL_HOST, settings.CONSUL_PORT)
    logger.info(f"注销 {service_id} 服务")
    register.deregister(service_id=service_id)
    logger.info("注销成功")
    sys.exit(0)


# 通过proto生成的文件 可能无法被pycharm感知到， 所以有可能不能被及时的同步到linux中
def get_free_tcp_port():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(("", 0))
    _, port = tcp.getsockname()
    tcp.close()
    return port


def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip',
                        nargs="?",
                        type=str,
                        default="127.0.0.1",
                        help="binding ip"
                        )
    parser.add_argument('--port',
                        nargs="?",
                        type=int,
                        default=50063,
                        help="the listening port"
                        )
    args = parser.parse_args()

    if args.port == 0:
        port = get_free_tcp_port()
    else:
        port = args.port

    logger.add("logs/inventory_srv_{time}.log")

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # 注册库存服务
    inventory_pb2_grpc.add_InventoryServicer_to_server(InventoryServicer(), server)

    # 注册健康检查
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)

    server.add_insecure_port(f'{args.ip}:{port}')

    import uuid
    service_id = str(uuid.uuid1())

    # 主进程退出信号监听
    """
        windows下支持的信号是有限的：
            SIGINT ctrl+C终端
            SIGTERM kill发出的软件终止
    """
    signal.signal(signal.SIGINT, partial(on_exit, service_id=service_id))
    signal.signal(signal.SIGTERM, partial(on_exit, service_id=service_id))

    logger.info(f"启动服务: {args.ip}:{port}")
    server.start()

    logger.info(f"服务注册开始")
    register = consul.ConsulRegister(settings.CONSUL_HOST, settings.CONSUL_PORT)
    if not register.register(name=settings.SERVICE_NAME, id=service_id,
                             address=args.ip, port=port, tags=settings.SERVICE_TAGS, check=None):
        logger.info(f"服务注册失败")

        sys.exit(0)
    logger.info(f"服务注册成功")

    # 启动之后还得监听rocketmq的对应的topic进行库存归还
    consumer = PushConsumer("mxshop_inventory")
    consumer.set_name_server_address(f"{settings.ROCKETMQ_HOST}:{settings.ROCKETMQ_PORT}")
    consumer.subscribe("order_reback", reback_inv)
    consumer.start()

    server.wait_for_termination()
    consumer.shutdown()


if __name__ == '__main__':
    logging.basicConfig()
    settings.client.add_config_watcher(settings.NACOS["DataId"], settings.NACOS["Group"], settings.update_cfg)
    serve()