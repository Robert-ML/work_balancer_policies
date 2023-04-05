import os
import random
import sys
import threading
import time
import typing

import json
from flask import Flask

# configuration
name   : str = ""
address: str = ""
port   : int = 0
location_l: int = 0
location_h: int = 0
performance: float = 0.0

# constants
config_file: str = "./config.json"

workers_key: str = "workers"
name_key   : str = "name"
address_key: str = "address"
port_key   : str = "port"
delays_key : str = "delays"
location_l_key   : str = "location_l"
location_h_key   : str = "location_h"
performance_key: str = "performance"

max_con_doing_work: int = 20
work_amount: float = 100.0
work_step: float = 3.0

# global vals
app: Flask = None # type: ignore
# max_connections: threading.Semaphore = threading.Semaphore(value=max_con_doing_work)
con_no_mutex: threading.Lock = threading.Lock()
con_no: int = 0

debug_con_no: int = 0

def inc_con_no() -> int:
    return _modif_con_no(+1)

def dec_con_no() -> int:
    return _modif_con_no(-1)

def _modif_con_no(a: int) -> int:
    global con_no_mutex
    global con_no

    ret: int = 0

    con_no_mutex.acquire()
    con_no += a
    ret = con_no
    con_no_mutex.release()

    return ret

def do_latency_delay():
    # delay communication time randomly
    # delay: float = random.uniform(location_l, location_h)
    # time.sleep(delay / 1000.0)

    # delay communication time fixed
    time.sleep(location_l / 1000.0)

def do_work():
    # global max_connections
    # max_connections.acquire()

    con_no: int = inc_con_no()

    work_remaining: float = work_amount

    # connection number penalty
    work_remaining *= (1 + 0.4 * (con_no / max_con_doing_work))

    # performance gain
    work_remaining /= performance

    # print(work_remaining)

    # convert to ms
    # print(f"#con: {con_no} | sleep: {work_remaining / 1000.0}")
    time.sleep(work_remaining / 1000.0)

    # while (work_remaining > 0):
    #     conn_no: int = 1
    #     with max_connections._cond: # type: ignore
    #         conn_no = max_con_doing_work - max_connections._value

    #     # if full under load get a 20% performance penalty
    #     performance_penaty: float = (1.0 - 0.2 * (conn_no / max_con_doing_work))
    #     # work done is a constant * server performance * performance penalty because of load
    #     work_done_now = work_step * performance * performance_penaty
    #     work_remaining -= work_done_now

    #     # print(f"name: {name}")
    #     # print(f"pp: {performance_penaty}")
    #     # print(f"wdn: {work_done_now}")
    #     # print(f"wr: {work_remaining}\n")

    #     time.sleep(work_step / 1000.0)

    dec_con_no()
    # max_connections.release()


def check_input_params() -> int:
    ret: int = 0

    if (len(sys.argv) < 2):
        print(f"usage: python3 {sys.argv[0]} <CONFIG_ID: uint>")
        ret = -1
    else:
        try:
            int(sys.argv[1])
        except ValueError:
            print(f"usage: python3 {sys.argv[0]} <CONFIG_ID: uint>")
            ret = -1

    if (os.path.isfile(config_file) == False):
        print(f"\"{config_file}\" file not found")
        ret = -1

    return ret

def load_configuration() -> int:
    global name
    global address
    global port
    global location_l
    global location_h
    global performance

    d: typing.Dict = {}
    with open(config_file) as f:
        d = json.load(f)

    if (type(d[workers_key]) != list):
        print(f"json format error: \"{workers_key}\" is not \'list\': {type(d[workers_key])}")
        return -1

    if (len(d[workers_key]) <= int(sys.argv[1])):
        print(f"configuration id (argv[1]) >= available configurations in {config_file}")

    config: typing.Dict = d[workers_key][int(sys.argv[1])]

    try:
        name    = config[name_key]
        address = config[address_key]
        port    = config[port_key]

        delays: typing.Dict = config[delays_key]
        location_l = delays[location_l_key]
        location_h = delays[location_h_key]
        performance = float(delays[performance_key])
    except any:
        print(f"error occured when extracting worker configuraiton from json file")
        return -1

    return 0

def main():
    if check_input_params() != 0:
        quit(-1)

    if load_configuration() != 0:
        quit(-2)

    # print(f"name: {name}")
    # print(f"address: {address}")
    # print(f"port: {port}")
    # print(f"location_l: {location_l}")
    # print(f"location_h: {location_h}")
    # print(f"performance: {performance}")

    global app
    app = Flask(name)

    @app.route('/compute', methods=["GET"])
    def compute():
        # global debug_con_no

        # debug_con_no += 1

        # print("\t#connections: " + str(debug_con_no))

        do_latency_delay()

        do_work()

        # print("\tdone #" + str(debug_con_no))
        # debug_con_no -= 1

        return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

    app.run(host = address, port = port, debug = False)



if __name__ == "__main__":
    main()
