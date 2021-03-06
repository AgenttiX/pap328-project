import typing as tp

import matplotlib.pyplot as plt
import numpy as np
import scipy.odr
from scipy.optimize import curve_fit

from devices.mca import MeasMCA
import plot
import stats
import type_hints

# Adjusting these may result in failed fits
THRESHOLD_LEVEL = 0.5
CUT_WIDTH_MULT = 1.7


# Functions to be fit

def poly1(x, a, b):
    return a*x + b


def poly2(x, a, b, c):
    return a*x**2 + b*x + c


# Other functions

def create_subplot_grid(
        num_plots: int,
        grid_aspect_ratio: float = 1,
        xlabel: str = None,
        ylabel: str = None) -> tp.Tuple[plt.Figure, tp.List[plt.Axes], int, int]:
    """Create a figure with a grid of subplots"""
    fig: plt.Figure
    num_plots_x = int(np.sqrt(num_plots)*grid_aspect_ratio)
    num_plots_y = int(np.ceil(num_plots / num_plots_x))
    fig, axes = plt.subplots(num_plots_y, num_plots_x)
    axes_flat: tp.List[plt.Axes] = [item for sublist in axes for item in sublist]

    # Remove unnecessary axes
    for ax in axes_flat[num_plots:]:
        fig.delaxes(ax)

    for i, ax in enumerate(axes_flat):
        if xlabel is not None:
            if num_plots - i <= num_plots_x:
                ax.set_xlabel(xlabel)
            else:
                ax.xaxis.set_ticklabels([])

            if i % num_plots_x == 0:
                ax.set_ylabel(ylabel)
            else:
                ax.yaxis.set_ticklabels([])

    return fig, axes_flat, num_plots_x, num_plots_y


def get_cut(
        data: np.ndarray,
        threshold_level: float = THRESHOLD_LEVEL,
        cut_width_mult: float = CUT_WIDTH_MULT) -> tp.Tuple[np.ndarray, int, int, float]:
    """Get cut parameters for fitting to a peak"""
    peak_ind: int = np.argmax(data)
    peak = data[peak_ind]
    threshold_inds = np.where(data > peak * threshold_level)[0]
    threshold_width = threshold_inds[-1] - threshold_inds[0]
    cut_ind_min = int(round(max(0, peak_ind - cut_width_mult * (peak_ind - threshold_inds[0]))))
    cut_ind_max = int(round(min(data.size, peak_ind + cut_width_mult * (threshold_inds[-1] - peak_ind) + 1)))
    cut_inds = np.arange(cut_ind_min, cut_ind_max)

    return cut_inds, threshold_width, peak_ind, peak


def fit_am(
        mca: MeasMCA,
        ax: plt.Axes,
        threshold_level: float = THRESHOLD_LEVEL,
        cut_width_mult: float = CUT_WIDTH_MULT,
        subtracted: np.ndarray = None,
        vlines: bool = True) -> type_hints.CURVE_FIT:
    """Fit the peaks of an Am-241 spectrum"""
    if subtracted is not None:
        counts = subtracted
    else:
        counts = mca.counts

    peak = np.max(counts)
    above_threshold = np.where(counts > threshold_level * peak)[0]
    half_ind = (above_threshold[0] + above_threshold[-1]) // 2
    filtered = counts.copy()
    filtered[:half_ind] = 0
    # ax.plot(filtered)

    cut_inds, threshold_width, peak_ind, peak = get_cut(filtered, threshold_level, cut_width_mult)

    # Vertical lines according to the cuts
    if vlines:
        # ax.scatter(peak_ind, peak, color="r")
        ax.vlines((cut_inds[0], cut_inds[-1]), ymin=0, ymax=peak, label="fit cut", colors="r", linestyles=":")

    fit = fit_mca_gaussian(mca, cut_inds, counts[cut_inds], peak, peak_ind, threshold_width)

    ax.plot(
        mca.channels,
        stats.gaussian_scaled_odr(fit[0], mca.channels),
        # fit[0][0] * stats.gaussian(mca.channels, *fit[0][1:]),
        linestyle="--",
        label="Fe-55 fit"
    )
    return fit


def fit_am_hv_scan(
        mcas: tp.List[MeasMCA],
        voltages: np.ndarray,
        gains: np.ndarray,
        fig_titles: bool = True,
        vlines: bool = True) -> tp.List[type_hints.CURVE_FIT]:
    """Create fits for the Am-241 HV scan measurements"""
    print("Fitting Am HV scan")
    fig, axes, num_plots_x, num_plots_y = create_subplot_grid(len(mcas), xlabel="MCA ch.", ylabel="Count")
    if fig_titles:
        fig.suptitle("Am fits")

    max_peak_height = np.max([np.max(mca.counts) for mca in mcas])
    max_ch = np.max([mca.channels[-1] for mca in mcas])
    y_adjust_step = 50
    max_peak_height_round = y_adjust_step * np.ceil(max_peak_height/y_adjust_step)

    fits = []
    for i, mca in enumerate(mcas):
        ax = axes[i]
        ax.plot(mca.counts)
        ax.set_xlim(0, max_ch)
        ax.set_ylim(0, max_peak_height_round)
        ax.text(0.05, 0.8, f"V={voltages[i]} V, g={gains[i]}", transform=ax.transAxes, fontdict={"size": 8})

        fits.append(fit_am(mca, ax, vlines=vlines))

    plot.save_fig(fig, "am_scan_fits")
    return fits


def fit_fe(
        mca: MeasMCA,
        ax: plt.Axes,
        threshold_level: float = THRESHOLD_LEVEL,
        cut_width_mult: float = CUT_WIDTH_MULT,
        secondary: bool = True,
        subtracted: np.ndarray = None,
        vlines: bool = True) \
        -> tp.Union[type_hints.CURVE_FIT, tp.Tuple[type_hints.CURVE_FIT, type_hints.CURVE_FIT]]:
    """Fit the peaks of an Fe-55 spectrum

    TODO: this could be combined to the HV scan fitting function
    """
    if subtracted is not None:
        counts = subtracted
    else:
        counts = mca.counts

    cut_inds, threshold_width, peak_ind, peak = get_cut(counts, threshold_level, cut_width_mult)

    fit = fit_mca_gaussian(mca, cut_inds, counts[cut_inds], peak, peak_ind, threshold_width)
    if not secondary:
        ax.plot(
            mca.channels,
            fit[0][0] * stats.gaussian(mca.channels, *fit[0][1:]),
            linestyle="--",
            label="Fe-55 fit"
        )
        return fit

    # The secondary peak is the Argon escape peak and therefore not a property of the Fe-55 source itself
    cut_inds2, threshold_width2, peak_ind2, peak2 = get_cut(counts[:cut_inds[0]-10], threshold_level, cut_width_mult)
    if vlines:
        ax.vlines((cut_inds2[0], cut_inds2[-1]), ymin=0, ymax=peak, label="fit cut", colors="r", linestyles=":")
    fit2 = fit_mca_gaussian(mca, cut_inds2, counts[cut_inds2], peak2, peak_ind2, threshold_width2)
    # print("fit:", fit)
    # print("fit2:", fit2)
    fit1_data = fit[0][0] * stats.gaussian(mca.channels, *fit[0][1:])
    fit2_data = fit2[0][0] * stats.gaussian(mca.channels, *fit2[0][1:])
    ax.plot(
        mca.channels,
        fit1_data + fit2_data,
        linestyle="--",
        label="Fe-55 fit",
    )
    return fit, fit2


def fit_fe_hv_scan(
        mcas: tp.List[MeasMCA],
        voltages: np.ndarray,
        gains: np.ndarray,
        threshold_level: float = THRESHOLD_LEVEL,
        cut_width_mult: float = CUT_WIDTH_MULT,
        fig_titles: bool = True,
        vlines: bool = True
        ) -> tp.List[type_hints.CURVE_FIT]:
    """Create fits for Fe-55 HV scan measurements"""
    print("Fitting Fe HV scan")
    fig, axes, num_plots_x, num_plots_y = create_subplot_grid(len(mcas), xlabel="MCA ch.", ylabel="Count")
    if fig_titles:
        fig.suptitle("Fe fits")
    # fig.tight_layout()

    # peak_channels = np.zeros(len(mcas))
    # fit_stds = np.zeros_like(peak_channels)

    max_peak_height = np.max([np.max(mca.counts) for mca in mcas])
    max_ch = np.max([mca.channels[-1] for mca in mcas])
    y_adjust_step = 50
    max_peak_height_round = y_adjust_step * np.ceil(max_peak_height/y_adjust_step)

    fits = []
    for i, mca in enumerate(mcas):
        ax = axes[i]
        ax.plot(mca.counts)

        ax.set_xlim(0, max_ch)
        ax.set_ylim(0, max_peak_height_round)
        ax.text(0.05, 0.8, f"V={voltages[i]} V, g={gains[i]}", transform=ax.transAxes, fontdict={"size": 8})

        fit = fit_fe(mca, ax, threshold_level, cut_width_mult, secondary=False, vlines=vlines)

        # Double Gaussian fitting is too error-prone
        # fit = curve_fit(
        #     stats.double_gaussian,
        #     cut_inds,
        #     mca.data[cut_inds],
        #     # p0=2*(peak/2, peak_ind, threshold_width)
        # )
        # if fit[0][0] > fit[0][3]:
        #     better_fit = fit[0][:3]
        # else:
        #     better_fit = fit[0][3:]
        # ax.plot(mca.channels, better_fit[0]*stats.gaussian(mca.channels, *better_fit[1:]))

        # peak_channels[i] = fit[0][1]
        # fit_stds[i] = fit[0][2]
        fits.append(fit)

    plot.save_fig(fig, "fe_scan_fits")

    return fits


def fit_manual(
        mca: MeasMCA,
        ax: plt.Axes,
        min_ind: int,
        max_ind: int,
        subtracted: np.ndarray = None,
        vlines: bool = True):
    """Fit the peaks of an Am-241 spectrum"""
    if subtracted is not None:
        counts = subtracted
    else:
        counts = mca.counts

    cut_inds = np.arange(min_ind, max_ind)
    peak_ind = min_ind + np.argmax(counts[cut_inds])
    peak = counts[peak_ind]
    threshold_width = max_ind - min_ind

    # Vertical lines according to the cuts
    if vlines:
        ax.vlines((cut_inds[0], cut_inds[-1]), ymin=0, ymax=peak, label="fit cut", colors="r", linestyles=":")

    fit = fit_mca_gaussian(mca, cut_inds, counts[cut_inds], peak, peak_ind, threshold_width)
    ax.plot(
        mca.channels,
        fit[0][0] * stats.gaussian(mca.channels, *fit[0][1:]),
        linestyle="--",
        label="Fe-55 fit"
    )
    return fit


def fit_odr(
        func: callable,
        x: np.ndarray, y: np.ndarray,
        std_x: tp.Union[float, np.ndarray] = None,
        std_y: np.ndarray = None,
        p0: tp.Union[tuple, np.ndarray] = None,
        debug: bool = False) -> type_hints.CURVE_FIT:
    """Generic ODR fitting

    Fitting function should have parameters of the form x, coeff1, coeff2 etc.
    """
    fit = curve_fit(func, x, y, p0=p0, sigma=std_y)
    if np.any(np.isinf(fit[1])):
        print("Warning! Least squares covariances could not be estimated. This may indicate a failed fit!")

    def func_odr(coeff, x):
        return func(x, *coeff)

    model = scipy.odr.Model(func_odr)
    data = scipy.odr.RealData(x=x, y=y, sx=std_x, sy=std_y)
    odr = scipy.odr.ODR(data, model, beta0=fit[0])
    out = odr.run()
    if debug:
        out.pprint()
    coeff = out.beta
    coeff_covar = out.cov_beta
    if not np.any(coeff_covar):
        print(
            "Warning! The ODR covariances could not be estimated, "
            "so reverting back to curve_fit results (both parameters and covariances)."
        )
        coeff = fit[0]
        coeff_covar = fit[1]
    # coeff_stds = out.sd_beta
    return coeff, coeff_covar


def fit_mca_gaussian(
        mca: MeasMCA, inds: np.ndarray, counts: np.ndarray,
        peak: float = None, peak_ind: float = None, threshold_width: float = None) -> type_hints.CURVE_FIT:
    """Get a Gaussian ODR fit for MCA data

    Result is in the same format as for scipy.optimize.curve_fit
    """
    if mca.diff_nonlin is None or mca.int_nonlin is None:
        raise ValueError("The MCA measurement should have nonlinearities configured")

    return fit_odr(
        stats.gaussian_scaled,
        inds, counts,
        std_x=mca.diff_nonlin,
        std_y=mca.int_nonlin * counts,
        p0=(peak, peak_ind, 0.4*threshold_width),
    )


def poly2_fit_text(fit: type_hints.CURVE_FIT, prec: str = "3e", err_prec: str = "3e") -> str:
    return \
        f"{fit[0][0]:.{prec}}±{fit[1][0, 0]:.{err_prec}}x^2 + " \
        f"{fit[0][1]:.{prec}}±{fit[1][1, 1]:.{err_prec}}x + " \
        f"{fit[0][2]:.{prec}}±{fit[1][2, 2]:.{err_prec}}"
