#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: redis_lock.py
# @time: 2021-10-30 22:35
# @author: jack
# @Email:793936517@qq.com
# @desc: 基于redis的锁 、一定要看懂源码

import threading

import redis
from datetime import datetime

from peewee import *
from playhouse.shortcuts import ReconnectMixin
from playhouse.pool import PooledMySQLDatabase
from inventory_srv.settings import settings


class ReconnectMySQLDatabase(ReconnectMixin, PooledMySQLDatabase):
    pass


db = ReconnectMySQLDatabase("mxshop_inventory_srv", host="192.168.0.104", port=3306, user="root", password="root")

# 删除 - 物理删除和逻辑删除 - 物理删除  -假设你把某个用户数据 - 用户购买记录，用户的收藏记录，用户浏览记录啊
# 通过save方法做了修改如何确保只修改update_time值而不是修改add_time
class BaseModel(Model):
    add_time = DateTimeField(default=datetime.now, verbose_name="添加时间")
    is_deleted = BooleanField(default=False, verbose_name="是否删除")
    update_time = DateTimeField(verbose_name="更新时间", default=datetime.now)

    def save(self, *args, **kwargs):
        # 判断这是一个新添加的数据还是更新的数据
        if self._pk is not None:
            # 这是一个新数据
            self.update_time = datetime.now()
        return super().save(*args, **kwargs)

    @classmethod
    def delete(cls, permanently=False):  # permanently表示是否永久删除
        if permanently:
            return super().delete()
        else:
            return super().update(is_deleted=True)

    def delete_instance(self, permanently=False, recursive=False, delete_nullable=False):
        if permanently:
            return self.delete(permanently).where(self._pk_expr()).execute()
        else:
            self.is_deleted = True
            self.save()

    @classmethod
    def select(cls, *fields):
        return super().select(*fields).where(cls.is_deleted == False)

    class Meta:
        database = settings.DB


#
# class Stock(BaseModel):
#     #仓库表
#     name = CharField(verbose_name="仓库名")
#     address = CharField(verbose_name="仓库地址")


class Inventory(BaseModel):
    # 商品的库存表
    # stock = PrimaryKeyField(Stock)
    goods = IntegerField(verbose_name="商品id", unique=True)
    stocks = IntegerField(verbose_name="库存数量", default=0)
    version = IntegerField(verbose_name="版本号", default=0)  # 分布式锁的乐观锁

import uuid
class Lock:
    def __init__(self, name, id=None):
        self.id = uuid.uuid4()
        self.redis_client = redis.Redis(host="192.168.0.104")
        self.name = name

    def acquire(self):
        if self.redis_client.set(self.name, self.id, nx=True, ex=15): #过期时间,如果不存在设置并且返回1，否在返回0， 这是原子操作
            #启动一个线程然后去定时的刷新这个过期 这个操作最好也是使用lua脚本来完成
            return True
        else:
            while True:
                import time
                time.sleep(1)
                if self.redis_client.set(self.name, self.id, nx=True, ex=15):
                    return True

    def release(self):
        #先做一个判断，先取出值来然后判断当前的值和你自己的lock中的id是否一致，如果一致删除，如果不一致报错
        #这块代码不安全， 将get和delete操作原子化 - 但是redis提供了一个脚本原因 - lua - nginx
        #使用lua脚本去完成这个操作使得该操作原子化
        id = self.redis_client.get(self.name)
        if id == self.id:
            self.redis_client.delete(self.name)
        else:
            print("不能删除不属于自己的锁")


def sell():
    # 多线程下的并发带来的数据不一致的问题
    goods_list = [(1, 10), (2, 20), (3, 30)]
    with db.atomic() as txn:
        # 超卖
        #续租过期时间 - 看门狗 - java中有一个redisson
        #如何防止我设置的值被其他的线程给删除掉
        for goods_id, num in goods_list:
            # 查询库存
            from inventory_srv.tests.py_redis_lock import Lock as PyLock
            redis_client = redis.Redis(host="192.168.0.104")
            lock = PyLock(redis_client, f"lock:goods_{goods_id}", auto_renewal=True, expire=15)
            lock.acquire()
            goods_inv = Inventory.get(Inventory.goods == goods_id)
            import time
            time.sleep(20)
            if goods_inv.stocks < num:
                print(f"商品：{goods_id} 库存不足")
                txn.rollback()
                break
            else:
                # 让数据库根据自己当前的值更新数据， 这个语句能不能处理并发的问题
                query = Inventory.update(stocks=Inventory.stocks - num).where(Inventory.goods == goods_id)
                ok = query.execute()
                if ok:
                    print("更新成功")
                else:
                    print("更新失败")
            lock.release()


if __name__ == "__main__":
    t1 = threading.Thread(target=sell)
    t2 = threading.Thread(target=sell)
    t1.start()
    t2.start()

    t1.join()
    t2.join()