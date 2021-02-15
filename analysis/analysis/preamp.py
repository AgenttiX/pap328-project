import os.path

import matplotlib.pyplot as plt
import numpy as np
from pandas.io.parsers import read_csv
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit

import plot

DATA_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PREAMP_FOLDER = os.path.join(DATA_FOLDER, "preamp")


def analyze_attenuator(
        path: str = os.path.join(DATA_FOLDER, "attenuator_test.csv"),
        fig_titles: bool = True):
    data = read_csv(path)
    att_setting = data["Attenuation setting"]
    a_in = data["Input A (V)"]
    a_out = data["Output A (V)"]
    attenuation = a_out / a_in
    print("Attenuation:", attenuation)

    fig: plt.Figure() = plt.figure()
    if fig_titles:
        fig.suptitle("Attenuator calibration")
    ax: plt.Axes = fig.add_subplot()
    ax.scatter(att_setting, attenuation)
    fit = curve_fit(
        lambda x, a, b: a*x + b,
        att_setting,
        attenuation
    )
    coeff = fit[0]
    coeff_stds = np.array([fit[1][0, 0], fit[1][1, 1]])
    ax.plot(
        att_setting,
        np.polyval(coeff, att_setting),
        label=f"fit (y = {coeff[0]:.3e}±{coeff_stds[1]:.3e}x + {coeff[1]:.3e}±{coeff_stds[1]:.3e})",
        color="tab:blue"
    )

    ax.set_xlabel("Attenuator setting")
    ax.set_ylabel("Attenuation")
    # ax.grid()
    ax.legend()
    plot.save_fig(fig, "attenuator")

    return attenuation


def analyze_preamp_freq_response(
        path: str = os.path.join(PREAMP_FOLDER, "preamp_frequency_response.csv"),
        fig_titles: bool = True):
    data = read_csv(path)
    f = data["f (Hz)"].to_numpy()
    a_in = data["Input A (V)"].to_numpy()
    a_out = data["Output A (V)"].to_numpy()
    gain = a_out / a_in
    spline = interp1d(f, gain, kind="cubic")
    f_axis = np.linspace(f[0], f[-1], 1000)

    x_mult = 1e-3
    fig: plt.Figure = plt.figure()
    if fig_titles:
        fig.suptitle("Frequency response of the pre-amplifier")
    ax: plt.Axes = fig.add_subplot()
    ax.scatter(f*x_mult, gain, label="data")
    ax.plot(f_axis*x_mult, spline(f_axis), label="cubic spline")

    ax.set_xlabel("Frequency (kHz)")
    ax.set_ylabel("Gain")
    plot.save_fig(fig, "preamp_freq_response")


def analyze_preamp_gain(
        attenuation,
        path: str = os.path.join(PREAMP_FOLDER, "gain_test.csv"),
        fig_titles: bool = True):
    data = read_csv(path)
    att_setting = data["Attenuation setting"].to_numpy()
    a_in = data["Input A (V)"].to_numpy()
    a_out = data["Output A (V)"].to_numpy()
    att_a_in = a_in * attenuation
    gain = a_out / att_a_in
    print("Gains:", gain)
    print("Gain mean:", np.mean(gain))
    print("Gain std:", np.std(gain))

    fig: plt.Figure = plt.figure()
    if fig_titles:
        fig.suptitle("Pre-amplifier gain")
    ax: plt.Axes = fig.add_subplot()
    ax.scatter(att_a_in, gain)
    ax.set_xlabel("Attenuated input amplitude (V)")
    ax.set_ylabel("Gain")
    plot.save_fig(fig, "preamp_gain")


if __name__ == "__main__":
    fig_titles = True
    analyze_preamp_freq_response(fig_titles=fig_titles)
    attenuation = analyze_attenuator(fig_titles=fig_titles)
    analyze_preamp_gain(attenuation, fig_titles=fig_titles)
    plt.show()
