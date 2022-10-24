import nacos

SERVER_ADDRESSES = "192.168.0.104:8848"
NAMESPACE = "c1872978-d51c-4188-a497-4e0cd20b97d5" #这里是namespace的id！！

# no auth mode
# client = nacos.NacosClient(SERVER_ADDRESSES, namespace=NAMESPACE)
# auth mode
client = nacos.NacosClient(SERVER_ADDRESSES, namespace=NAMESPACE, username="nacos", password="nacos")

# get config
data_id = "user-srv.json"
group = "dev"
print(type(client.get_config(data_id, group)))  #返回的是字符串
import json
json_data = json.loads(client.get_config(data_id, group))
print(json_data)


def test_cb(args):
    print("配置文件产生变化")
    print(args)




if __name__ == "__main__":

    client.add_config_watcher(data_id, group, test_cb)
    import time

    time.sleep(3000)