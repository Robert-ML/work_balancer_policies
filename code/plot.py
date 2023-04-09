import typing
import matplotlib.pyplot as plt
import numpy as np
import pickle

def main():
    file_in = open(r"./data.pkl", "rb")
    data = pickle.load(file_in)
    file_in.close()

    plot(data)

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
    w: float = 0.15

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
    ax.set_title("Work Balancer Policies compared (lower is better)")

    plt.show()

if __name__ == "__main__":
    main()
