"""
Copyright 2022 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/XXXXXXXXX

This module contains code related to making a distance distribution using the assembly-vs-assembly
alignments.

This file is part of XXXXXXXXX. XXXXXXXXX is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. XXXXXXXXX is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with XXXXXXXXX.
If not, see <https://www.gnu.org/licenses/>.
"""

import collections
import itertools
import math
import numpy as np
import re
import statistics
import sys

from .intrange import IntRange
from .misc import get_fasta_size, get_n50


def get_distribution(args, alignments, assembly_filename_a):
    """
    Uses the alignments to build a distance distribution.
    """
    if args.ignore_indels:
        all_cigars = [remove_indels(a.expanded_cigar) for a in alignments]
    else:
        all_cigars = [compress_indels(a.expanded_cigar) for a in alignments]

    n50_alignment_length = get_n50(len(c) for c in all_cigars)

    aligned_frac = get_query_coverage(alignments, assembly_filename_a)
    window_size, window_step = choose_window_size_and_step(all_cigars, args.window_count)
    all_cigars = [c for c in all_cigars if len(c) >= window_size]
    distances, max_difference_count = get_distances(all_cigars, window_size, window_step)
    distance_counts = collections.Counter(distances)

    masses = [0 if distance_counts[i] == 0 else distance_counts[i] / len(distances)
              for i in range(max_difference_count + 1)]
    mean_identity = 1.0 - get_distance(masses, window_size, 'mean')

    log_text = [f'  N50 alignment length: {n50_alignment_length}',
                f'  aligned fraction: {100.0 * aligned_frac:.2f}%',
                f'  mean identity: {100.0 * mean_identity:.2f}%',
                f'  distances sampled from {len(distances)} x {window_size} bp windows']

    return masses, aligned_frac, window_size, log_text


def choose_window_size_and_step(cigars, target_window_count):
    """
    This function chooses an appropriate window size and step for the given CIGARs. It tries to
    balance larger windows, which give higher-resolution identity samples, especially with
    closely-related assemblies, and smaller windows, which allow for more identity samples.
    """
    window_step = 1000
    while window_step > 1:
        window_size = window_step * 100
        if get_window_count(cigars, window_size, window_step) > target_window_count:
            return window_size, window_step
        window_step -= 1
    return window_step * 100, window_step


def get_window_count(cigars, window_size, window_step):
    """
    For a given window size, window step and set of CIGARs, this function returns how many windows
    there will be in total.
    """
    count = 0
    for cigar in cigars:
        cigar_len = len(cigar)
        if cigar_len < window_size:
            continue
        cigar_len -= window_size
        count += 1
        count += cigar_len // window_step
    return count



def get_query_coverage(alignments, assembly_filename):
    assembly_size = get_fasta_size(assembly_filename)
    ranges_by_contig = {}
    for a in alignments:
        if a.query_name not in ranges_by_contig:
            ranges_by_contig[a.query_name] = IntRange()
        ranges_by_contig[a.query_name].add_range(a.query_start, a.query_end)
    aligned_bases = sum(r.total_length() for r in ranges_by_contig.values())
    assert aligned_bases <= assembly_size
    return aligned_bases / assembly_size


def get_distances(all_cigars, window_size, window_step):
    distances, max_difference_count = [], 0
    for cigar in all_cigars:
        # TODO: trim CIGAR so windows fit in the middle?
        start, end = 0, window_size
        while end <= len(cigar):
            cigar_window = cigar[start:end]
            assert len(cigar_window) == window_size
            difference_count = get_difference_count(cigar_window)
            distances.append(difference_count)
            max_difference_count = max(max_difference_count, difference_count)
            start += window_step
            end += window_step
    return distances, max_difference_count


def remove_indels(cigar):
    """
    Removes all indels from a CIGAR. For example:
    in:  ===X=IIII==XX==DDDD==
    out: ===X===XX====
    """
    return re.sub(r'I+', '', re.sub(r'D+', '', cigar))


def compress_indels(cigar):
    """
    Compresses runs of indels into size-1 indels. For example:
    in:  ===X=IIII==XX==DDDD==
    out: ===X=I==XX==D==
    """
    return re.sub(r'I+', 'I', re.sub(r'D+', 'D', cigar))


def get_difference_count(cigar):
    """
    Returns the number of mismatches and indels in the CIGAR.
    """
    return cigar.count('X') + cigar.count('I') + cigar.count('D')


def get_distance(masses, piece_size, method):
    if method == 'mean':
        d = get_mean(masses)
    elif method == 'median':
        d = get_interpolated_median(masses)
    elif method == 'mode':
        d = get_mode(masses)
    elif method == 'peak':
        d, _ = get_peak_distance(masses)
    else:
        assert False
    return d / piece_size


def get_mean(masses):
    return np.average(range(len(masses)), weights=masses)


def get_median(masses):
    """
    Returns the median of the distance distribution. This median is not interpolated, i.e. it will
    be equal to one of the distances in the distribution.
    """
    half_total_mass = sum(masses) / 2.0
    total = 0.0
    for i, m in enumerate(masses):
        total += m
        if total >= half_total_mass:
            return i
    return 0


def get_interpolated_median(masses):
    """
    Returns the interpolated median of the distance distribution:
    https://en.wikipedia.org/wiki/Median#Interpolated_median
    https://aec.umich.edu/median.php
    """
    median = get_median(masses)
    below, equal, above = 0.0, 0.0, 0.0
    for i, m in enumerate(masses):
        if i < median:
            below += m
        elif i > median:
            above += m
        else:  # i == median
            equal += m
    if equal == 0.0:
        interpolated_median = median
    else:
        interpolated_median = median + ((above - below) / (2.0 * equal))
    return interpolated_median


def get_mode(masses):
    """
    Returns the mode of the distance distribution (the distance with the highest mass). If multiple
    distances tie for the highest mass (the distribution is multimodal), it returns the mean of
    those distances.
    """
    max_mass = max(masses)
    distances_with_max_mass = []
    for i, m in enumerate(masses):
        if m == max_mass:
            distances_with_max_mass.append(i)
    if len(distances_with_max_mass) == 1:
        return distances_with_max_mass[0]
    else:
        return statistics.mean(distances_with_max_mass)


def add_self_distances(distances, aligned_fractions, sample_names):
    for n in sample_names:
        distances[(n, n)] = 0.0
        aligned_fractions[(n, n)] = 1.0


def check_matrix_size(distances, sample_names, alignment_results):
    if len(distances) != len(sample_names)**2:
        sys.exit(f'\nError: incorrect number of records in {alignment_results}'
                 f' - rerun XXXXXXXXX align')


def correct_distances(distances, aligned_fractions, sample_names, correction):
    if 'jukescantor' in correction:
        for a in sample_names:
            for b in sample_names:
                distances[(a, b)] = jukes_cantor(distances[(a, b)])
    if 'alignedfrac' in correction:
        for a in sample_names:
            for b in sample_names:
                distances[(a, b)] = distances[(a, b)] / aligned_fractions[(a, b)]


def jukes_cantor(d):
    """
    https://www.desmos.com/calculator/okovk3dipx
    """
    if d == 0.0:
        return 0.0
    if d >= 0.75:
        return 25.0
    return -0.75 * math.log(1.0 - 1.3333333333333 * d)


def make_symmetrical(distances, sample_names):
    for a, b in itertools.combinations(sample_names, 2):
        d1 = distances[(a, b)]
        d2 = distances[(b, a)]
        mean_distance = (d1 + d2) / 2.0
        distances[(a, b)] = mean_distance
        distances[(b, a)] = mean_distance


def output_phylip_matrix(distances, sample_names):
    print(len(sample_names))
    for a in sample_names:
        print(a, end='')
        for b in sample_names:
            print(f'\t{distances[(a, b)]:.8f}', end='')
        print()


def get_peak_distance(smoothed_masses, window_size):
    """
    Starts with the median and climb upwards, smoothing when a peak is reached. If a lot of
    smoothing doesn't change the peak, the process stops.

    The final returned value is interpolated from the peak and its neighbours.
    """
    log_text = ['  mass peaks:']
    peaks_with_total_mass = [(get_peak_total_mass(smoothed_masses, p)[0], p)
                             for p in find_peaks(smoothed_masses)]
    most_massive_peak = sorted(peaks_with_total_mass)[-1][1]
    for mass, peak in peaks_with_total_mass:
        star = ' *' if peak == most_massive_peak else ''
        log_text.append(f'    {peak/window_size:.9f} ({100.0 * mass:.1f}%){star}')

    # Get the lower and upper bounds of the peak.
    _, low, high = get_peak_total_mass(smoothed_masses, most_massive_peak)

    return most_massive_peak, low, high, log_text


def climb_to_peak(masses, starting_point):
    peak = starting_point
    while True:
        lower_mass = masses[peak-1] if peak > 0 else float('-inf')
        higher_mass = masses[peak+1] if peak < len(masses)-1 else float('-inf')
        if lower_mass >= masses[peak] and lower_mass > higher_mass:
            peak -= 1
        elif higher_mass > masses[peak] and higher_mass > lower_mass:
            peak += 1
        else:
            break
    return peak


def interpolate(low, peak, high):
    """
    This function takes three masses as input: the mass below the peak, the mass at the peak and
    the mass above the peak (i.e. it assumes that the below/above masses are no larger than the
    peak mass). It then returns an interpolation adjustment that varies from -0.5 to 0.5, similar
    to how interpolated medians work.
    """
    try:
        return (high - low) / (2.0 * (peak - min(low, peak, high)))
    except ZeroDivisionError:
        return 0.0


def smooth_distribution(masses, iterations=1000):
    """
    Smooths the mass distribution with a force-directed approach. Each point is pulled by two
    forces:
    * Trying to get close to the empirical point
    * Trying to get close to the neighbouring points.
    """
    smoothed = masses.copy()
    for _ in range(iterations):
        for i, m in enumerate(masses):

            # The first force pulls the point back to the empirical distribution, but it's squared,
            # so small deviations are okay.
            difference = m - smoothed[i]
            force_1 = difference * abs(difference)

            # The second force
            lower = smoothed[i-1] if i > 0 else None
            upper = smoothed[i+1] if i < len(masses)-1 else None
            if lower is not None and upper is not None:
                mean_neighbour = (lower + upper) / 2.0
                force_2 = mean_neighbour - smoothed[i]
                force_2_scaling_factor = get_force_scaling_factor(i)
                force_2 *= force_2_scaling_factor
            else:
                force_2 = 0.0

            smoothed[i] += force_1
            smoothed[i] += force_2

    # Normalise to sum to one.
    total = sum(smoothed)
    smoothed = [s/total for s in smoothed]

    return smoothed


def get_force_scaling_factor(i):
    """
    https://www.desmos.com/calculator/xyxaykwudg
    """
    scaling_factor = 2.0 ** (-100.0 / (i+5.0)) - 0.0005
    return max(scaling_factor, 0.0)


def find_peaks(masses):
    """
    Given a mass distribution, this returns a list of all peaks indices.
    """
    peaks = []
    for i, m in enumerate(masses):

        # If the point is not greater than the left-neighbour, move on.
        if not (True if i == 0 else m > masses[i-1]):
            continue

        # If the point is also greater than the right-neighbour, it's definitely a peak.
        if True if i == len(masses)-1 else m > masses[i+1]:
            peaks.append(i)
            continue

        # If the point is equal to its right-neighbour, then we need to check whether there is a
        # multi-point peak. If so, we add the middle position of the multi-point peak (rounded
        # down).
        if m == masses[i+1]:
            j = i
            while j < len(masses) and masses[j] == m:
                j += 1
            if j == len(masses) or m > masses[j]:
                peaks.append(int((i+j-1)/2))

    return peaks


def get_peak_total_mass(masses, peak):
    """
    Given a mass distribution and peak index, this returns the total mass of the peak by extending
    in both directions until the masses rise.
    """
    total = masses[peak]

    # Add masses on the left side of the peak.
    previous_mass = masses[peak]
    low = peak-1
    while low >= 0 and masses[low] <= previous_mass:
        total += masses[low]
        previous_mass = masses[low]
        low -= 1

    # Add masses on the right side of the peak.
    previous_mass = masses[peak]
    high = peak+1
    while high < len(masses) and masses[high] <= previous_mass:
        total += masses[high]
        previous_mass = masses[high]
        high += 1

    return total, low, high
