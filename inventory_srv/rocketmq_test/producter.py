#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: producter.py
# @time: 2021-10-30 22:13
# @author: jack
# @Email:793936517@qq.com
# @desc:

from rocketmq.client import Producer, Message

topic = "order_reback"


def create_message():
    msg = Message(topic)
    msg.set_delay_time_level(4)
    msg.set_keys("imooc")
    msg.set_tags('bobby')
    msg.set_property("name", "micro services")
    msg.set_body("订单取消")
    return msg


def send_message_sync(count):
    producer = Producer("test")
    producer.set_name_server_address("127.0.0.1:9876")

    #首先要启动producer
    producer.start()
    for n in range(count):
        msg = create_message()
        ret = producer.send_sync(msg)
        print(f"发送状态:{ret.status}, 消息id:{ret.msg_id}")
    print("消息发送完成")
    producer.shutdown()


if __name__ == "__main__":
    #发送普通消息
    send_message_sync(5)