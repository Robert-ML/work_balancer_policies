import aiohttp
import asyncio
import json
import os
import random
import sys
import time
import typing


class Machine:
    def __init__(self, name: str, address: str, port: int) -> None:
        self.name   : str = name
        self.address: str = address
        self.port   : int = port
        self.conn_no: int = 0

    def __repr__(self) -> str:
        return f"[{self.name}, {self.address}, {self.port}]"

    def __str__(self) -> str:
        return f"[{self.name}, {self.address}, {self.port}]"


# configuration
name: str = ""
workers: typing.List[Machine] = []

rr_weights_per_machine: typing.List[int] = []
lc_weights_per_machine: typing.List[float] = []


# constants
config_file: str = "./config.json"

workers_key       : str = "workers"
worker_name_key   : str = "name"
worker_address_key: str = "address"
worker_port_key   : str = "port"

balancer_key     : str = "balancer"
balancer_name_key: str = "name"
rr_wpm_key: str = "rr_weights_per_machine" # Round Robin
lc_wpm_key: str = "lc_weights_per_machine" # Least Connections with weights


# global variables
machine_index: int = 0
rr_weights: typing.List[int] = [] # variable used when running the benchmark
responses_time: typing.List[float] = []

def main():
    if check_input_params() != 0:
        quit(-1)

    if load_configuration() != 0:
        quit(-2)

    print(f"name: {name}")
    print(f"workers: {workers}")
    print(f"rr_weights_per_machine: {rr_weights_per_machine}")
    print(f"lc_weights_per_machine: {lc_weights_per_machine}")

    benchmark_repeated()

def check_input_params() -> int:
    ret: int = 0

    policy_usage_msg: str = "policies:\n"\
    "\t1 - Random\n"\
    "\t2 - Round Robin\n"\
    "\t3 - Weighted Round Robin\n"\
    "\t4 - Least connections\n"\
    "\t5 - Least connections with weights\n"

    if (len(sys.argv) < 4):
        print(f"usage: python3 {sys.argv[0]} <policy: uint> <req_no: uint> <repetitions: uint>\n"\
        + policy_usage_msg, end="")

        ret = -1
    else:
        try:
            int(sys.argv[1])
            int(sys.argv[2])
            int(sys.argv[3])
        except ValueError:
            print(f"usage: python3 {sys.argv[0]} <policy: uint> <req_no: uint> <repetitions: uint>\n"\
            + policy_usage_msg, end="")

            ret = -1

    if (int(sys.argv[1]) < 1 or int(sys.argv[1]) > 5):
        print(f"wrong policy number, usage:python3 {sys.argv[0]} <policy: uint> <req_no: uint> <repetitions: uint>\n"\
            + policy_usage_msg, end="")

        ret = -1

    if (os.path.isfile(config_file) == False):
        print(f"\"{config_file}\" file not found")
        ret = -1

    return ret

def load_configuration() -> int:
    global name
    global workers
    global rr_weights_per_machine
    global lc_weights_per_machine

    global rr_weights

    d: typing.Dict = {}
    with open(config_file) as f:
        d = json.load(f)

    # load benchmark configuration
    if (type(d[balancer_key]) != dict):
        print(f"json format error: \"{balancer_key}\" is not \'dict\': {type(d[balancer_key])}")
        return -1

    balancer_config: typing.Dict = d[balancer_key]
    try:
        name = balancer_config[balancer_name_key]
        rr_weights_per_machine = balancer_config[rr_wpm_key]
        lc_weights_per_machine = balancer_config[lc_wpm_key]

        rr_weights = rr_weights_per_machine.copy()

    except any:
        print(f"error occured when extracting benchmarker configuration from json file")
        return -1



    # load worker machine configuration
    if (type(d[workers_key]) != list):
        print(f"json format error: \"{workers_key}\" is not \'list\': {type(d[workers_key])}")
        return -1
    if (len(d[workers_key]) <= int(sys.argv[1])):
        print(f"configuration id (argv[1]) >= available configurations in {config_file}")

    machines_configs: typing.List = d[workers_key]
    try:
        for machine_config in machines_configs:
            machine_name: str = machine_config[worker_name_key]
            machine_addr: str = machine_config[worker_address_key]
            machine_port: int = int(machine_config[worker_port_key])

            new_machine: Machine = Machine(machine_name, machine_addr, machine_port)

            workers.append(new_machine)
    except any:
        print(f"error occured when extracting worker addresses and ports from json file")
        return -1

    return 0

def benchmark_repeated():
    for x in range(int(sys.argv[3])):
        asyncio.run(benchmark())

async def benchmark():

    async with aiohttp.ClientSession() as session:
        tasks: typing.List = []

        for _ in range(int(sys.argv[2])):
            machine_ind = balancing_policy(int(sys.argv[1]))
            tasks.append(asyncio.ensure_future(get_work_done(session, machine_ind)))

        await asyncio.gather(*tasks)

        print(sum(responses_time) / len(responses_time))


def balancing_policy(pol_no: int) -> int:
    global machine_index

    # Random
    if (pol_no == 0):
        return random.randrange(0, len(workers))

    # Round Robin
    elif (pol_no == 1):
        ret: int = machine_index
        machine_index = (machine_index + 1) % len(workers)
        return ret

    # Weighted Round Robin
    elif (pol_no == 2):
        global rr_weights

        ret: int = machine_index
        rr_weights[machine_index] -= 1

        if (rr_weights[machine_index] == 0):
            rr_weights[machine_index] = rr_weights_per_machine[machine_index]
            machine_index = (machine_index + 1) % len(workers)

        return ret

    # Least connections
    elif (pol_no == 3):
        return get_least_con_machine()

    # Least connections with weights
    elif (pol_no == 4):
        return get_least_con_machine(True)

    print("[ERROR]: shouldn't have reached here")
    quit(-3)

async def get_work_done(session, machine_ind: int):
    global workers
    global responses_time

    url: str = f"http://{workers[machine_ind].address}:{workers[machine_ind].port}/compute"
    workers[machine_ind].conn_no += 1

    start_time: float = time.time()

    async with session.get(url) as resp:
        end_time: float = time.time()

    workers[machine_ind].conn_no -= 1
    responses_time.append(end_time - start_time)


def get_least_con_machine(with_weights: bool = False) -> int:
    # populate the default minimum
    min_con: float = 0
    if with_weights == False:
        min_con = workers[0].conn_no
    else:
        min_con = workers[0].conn_no * lc_weights_per_machine[0]
    min_ind: int = 0

    # look for the actual minimum
    for i in range(1, len(workers)):
        if with_weights == False:
            if min_con > workers[i].conn_no:
                min_con = workers[i].conn_no
                min_ind = i
        else:
            if min_con > workers[i].conn_no * lc_weights_per_machine[i]:
                min_con = workers[i].conn_no * lc_weights_per_machine[i]
                min_ind = i

    return min_ind


if __name__ == "__main__":
    main()
