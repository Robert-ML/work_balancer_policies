import aiohttp
import asyncio
import json
import os
import random
import sys
import time
import typing
import matplotlib.pyplot as plt
import numpy as np
import threading

class Machine:
    def __init__(self, name: str, address: str, port: int) -> None:
        self.name   : str = name
        self.address: str = address
        self.port   : int = port
        self.conn_no: int = 1
        self.conn_no_lock: threading.Lock = threading.Lock()

    def __repr__(self) -> str:
        return f"[{self.name}, {self.address}, {self.port}]"

    def __str__(self) -> str:
        return f"[{self.name}, {self.address}, {self.port}]"

    def get_conn_no(self) -> int:
        ret: int = 1
        self.conn_no_lock.acquire()
        ret = self.conn_no
        self.conn_no_lock.release()
        return ret

    def inc_conn_no(self) -> int:
        return self.__modif_con_no(+1)

    def dec_conn_no(self) -> int:
        return self.__modif_con_no(-1)

    def __modif_con_no(self, a: int) -> int:
        ret: int = 1
        self.conn_no_lock.acquire()
        self.conn_no += a
        ret = self.conn_no
        self.conn_no_lock.release()
        return ret


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

# plotting
responses_time: typing.List[float] = []

# [ (request_no, [ measurement of each policy [multiple runs] ] ) ]
measurements: typing.List[typing.Tuple[int, typing.List[typing.List[float]]]] = []


def main():
    if check_input_params() != 0:
        quit(-1)

    if load_configuration() != 0:
        quit(-2)

    print(f"name: {name}")
    print(f"workers: {workers}")
    print(f"rr_weights_per_machine: {rr_weights_per_machine}")
    print(f"lc_weights_per_machine: {lc_weights_per_machine}")

    arg_req_no: int = int(sys.argv[2])
    req_nos: typing.List[int] = [int(arg_req_no * 0.25), int(arg_req_no * 0.50), int(arg_req_no * 0.75), int(arg_req_no * 1.00), int(arg_req_no * 1.25)]
    # req_nos: typing.List[int] = [int(arg_req_no * 1.00)]

    pol_no: int = int(sys.argv[1])

    global measurements

    if pol_no == 0:
        for req_no in req_nos:
            print("#requests: " + str(req_no))
            measurement_of_each_policy: typing.List[typing.List[float]] = []

            for policy in range(1, 6):
                print("\tpolicy: " + str(policy))
                measurement_of_each_policy.append(benchmark_repeated(policy, req_no))

            measurements.append( (req_no, measurement_of_each_policy) )

    else:
        for req_no in req_nos:
            measurements.append( (req_no, [ benchmark_repeated(pol_no, req_no) ]) )

    plot(measurements)

def check_input_params() -> int:
    ret: int = 0

    policy_usage_msg: str = "policies:\n"\
    "\t0 - Test all policies and plot the comparison"\
    "\t1 - Random\n"\
    "\t2 - Round Robin\n"\
    "\t3 - Weighted Round Robin\n"\
    "\t4 - Least connections\n"\
    "\t5 - Weighted least connections\n"

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

    if (int(sys.argv[1]) < 0 or int(sys.argv[1]) > 5):
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

        rr_weights = [int(x) for x in rr_weights_per_machine]

    except any:
        print(f"error occured when extracting benchmarker configuration from json file")
        return -1



    # load worker machine configuration
    if (type(d[workers_key]) != list):
        print(f"json format error: \"{workers_key}\" is not \'list\': {type(d[workers_key])}")
        return -1

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

def benchmark_repeated(pol_no: int, req_no: int) -> typing.List[float]:
    global responses_time

    ret: typing.List[float] = []
    for i in range(int(sys.argv[3])):
        print("\t\trun" + str(i))

        asyncio.run(benchmark(pol_no, req_no))
        new_measured_avg_time: float = 0
        if len(responses_time) == 0:
            new_measured_avg_time = 0.00
        else:
            new_measured_avg_time = round(sum(responses_time) / len(responses_time), 2)

        ret.append(new_measured_avg_time)
        responses_time = []

        time.sleep(5)

    return ret


async def benchmark(pol_no: int, req_no: int):

    async with aiohttp.ClientSession() as session:
        tasks: typing.List = []

        for _ in range(req_no):
            machine_ind = balancing_policy(pol_no)
            workers[machine_ind].inc_conn_no()
            tasks.append(asyncio.ensure_future(get_work_done(session, machine_ind)))

        await asyncio.gather(*tasks)

        if len(responses_time) == 0:
            print("0.00")
        else:
            print(round(sum(responses_time) / len(responses_time), 2))

def balancing_policy(pol_no: int) -> int:
    global machine_index

    # Random
    if (pol_no == 1):
        return random.randrange(0, len(workers))

    # Round Robin
    elif (pol_no == 2):
        ret: int = machine_index
        machine_index = (machine_index + 1) % len(workers)
        return ret

    # Weighted Round Robin
    elif (pol_no == 3):
        global rr_weights

        ret: int = machine_index
        rr_weights[machine_index] -= 1

        if (rr_weights[machine_index] == 0):
            rr_weights[machine_index] = rr_weights_per_machine[machine_index]
            machine_index = (machine_index + 1) % len(workers)

        return ret

    # Least connections
    elif (pol_no == 4):
        return get_least_con_machine()

    # Least connections with weights
    elif (pol_no == 5):
        return get_least_con_machine(True)

    print("[ERROR]: shouldn't have reached here")
    quit(-3)

async def get_work_done(session, machine_ind: int):
    global workers
    global responses_time

    url: str = f"http://{workers[machine_ind].address}:{workers[machine_ind].port}/compute"

    start_time: float = time.time()

    async with session.get(url) as resp:
        end_time: float = time.time()

    workers[machine_ind].dec_conn_no()
    responses_time.append(end_time - start_time)

def get_least_con_machine(with_weights: bool = False) -> int:
    # populate the default minimum
    min_con: float = 0.0

    w0_con_no: int = workers[0].get_conn_no()
    # print(f" 0: {w0_con_no} |", end="")
    if with_weights == False:
        min_con = w0_con_no
    else:
        min_con = w0_con_no * lc_weights_per_machine[0]
    min_ind: int = 0

    # look for the actual minimum
    for i in range(1, len(workers)):
        wi_con_no: int = workers[i].get_conn_no()
        # print(f" {i}: {wi_con_no} |", end="")
        if with_weights == False:
            if min_con > wi_con_no:
                min_con = wi_con_no
                min_ind = i
        else:
            if min_con > wi_con_no * lc_weights_per_machine[i]:
                min_con = wi_con_no * lc_weights_per_machine[i]
                min_ind = i

    # print("")

    return min_ind

def plot(data: typing.List[typing.Tuple[int, typing.List[typing.List[float]]]]):
    x_labels: typing.List[int] = []
    policies_labels: typing.List[str] = ["Random", "Round Robin", "Weighted Round Robin", "Least connections", "Weighted least connections"]

    policies_mean: typing.List[typing.List[float]] = [[] for _ in range(len(data[0][1]))]
    policies_mean_v: typing.List[typing.List[float]] = [[] for _ in range(len(data[0][1]))]

    for (req_no, policies_measurements) in data:
        x_labels.append(req_no)

        for i, policy_measurement in enumerate(policies_measurements):
            policies_mean[i].append(round(sum(policy_measurement) / len(policy_measurement), 2))
            policies_mean_v[i].append(np.array(policy_measurement).var())


    _, ax = plt.subplots()

    x = np.arange(len(x_labels))
    w: float = 0.10

    L: int = int(len(policies_mean) / 2)
    widths: typing.List[float] = [(-L * w + i * w + (((len(policies_mean) + 1) % 2) * (w / 2))) for i in range(len(policies_mean))]

    bars: typing.List[typing.Any] = []
    for i, pol in enumerate(policies_mean):
        bars.append(ax.bar(x + widths[i], pol, w, label=policies_labels[i], yerr=policies_mean_v[i]))

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.legend()

    for bar in bars:
        ax.bar_label(bar, padding=3)

    ax.set_xlabel("#requests")
    ax.set_ylabel("avg. time (ms) / request")

    plt.show()


if __name__ == "__main__":
    main()
