#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file: user.py
# @time: 2021-10-24 15:15
# @author: jack
# @Email:793936517@qq.com
# @desc:

import grpc

from user_srv.proto import user_pb2_grpc, user_pb2


class UserTest:
    def __init__(self):
        #连接grpc服务器
        channel = grpc.insecure_channel("127.0.0.1:50061")
        self.stub = user_pb2_grpc.UserStub(channel)

    def user_list(self):
        rsp: user_pb2.UserListResonse = self.stub.GetUserList(user_pb2.PageInfo(pn=1, pSize=2))
        print(rsp.total)
        for user in rsp.data:
            print(user.mobile, user.birthday)

    def get_user_by_id(self, id):
        rsp: user_pb2.UserInfoResponse = self.stub.GetUserById(user_pb2.IdRequest(id=id))
        print(rsp.mobile)

    def create_user(self, name, mobile, password):
        rsp: user_pb2.UserInfoResponse = self.stub.CreateUser(user_pb2.CreateUserInfo(
            name=name,
            password=password,
            mobile=mobile
        ))
        print(rsp.id)


if __name__ == "__main__":
    user = UserTest()
    user.user_list()
    # user.get_user_by_id(100)

    # user.create_user("bobby", "18787878787", "admin123")
