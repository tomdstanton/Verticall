"""
Copyright 2022 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/Verticall

This file is part of Verticall. Verticall is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. Verticall is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with Verticall.
If not, see <https://www.gnu.org/licenses/>.
"""

import matplotlib.pyplot as plt
import pandas as pd
from plotnine import ggplot, aes, geom_segment, geom_line, geom_vline, labs, theme_bw, \
    scale_x_continuous, scale_x_sqrt, scale_y_continuous, scale_y_sqrt, scale_color_manual, \
    element_blank, theme, annotate
import warnings

from .distance import get_distance

warnings.filterwarnings('ignore')

VERTICAL_COLOUR = '#4859a0'
VERTICAL_COLOUR_LIGHT = '#aabbf2'
HORIZONTAL_COLOUR = '#c47e7e'
HORIZONTAL_COLOUR_LIGHT = '#eac7c7'
AMBIGUOUS_COLOUR = '#c9c9c9'


def show_plots(sample_name_a, sample_name_b, alignments, window_size, masses, smoothed_masses,
               thresholds, vertical_masses, horizontal_masses, painted_a, sqrt_distance,
               sqrt_mass):
    fig_1 = distribution_plot_1(sample_name_a, sample_name_b, window_size, masses, smoothed_masses,
                                thresholds, sqrt_distance, sqrt_mass)
    fig_2 = distribution_plot_2(sample_name_a, sample_name_b, window_size, vertical_masses,
                                horizontal_masses, sqrt_distance, sqrt_mass)
    fig_3 = alignment_plot(sample_name_a, sample_name_b, alignments, window_size, sqrt_distance)
    fig_4 = contig_plot(sample_name_a, painted_a, window_size, sqrt_distance)

    plt.show()


def distribution_plot_1(sample_name_a, sample_name_b, window_size, masses,
                        smoothed_masses, thresholds, sqrt_distance, sqrt_mass):
    title = f'{sample_name_a} vs {sample_name_b} full distribution with thresholds'
    mean = get_distance(masses, window_size, 'mean')
    median = get_distance(masses, window_size, 'median')
    x_max = len(masses) / window_size
    y_max = 1.05 * max(max(masses), max(smoothed_masses))
    distances = [i / window_size for i in range(len(masses))]
    grouping = group_using_thresholds(masses, thresholds)

    df = pd.DataFrame(list(zip(distances, masses, smoothed_masses, grouping)),
                      columns=['distance', 'mass', 'smoothed_mass', 'grouping'])

    g = (ggplot(df) +
         geom_segment(aes(x='distance', xend='distance', y=0, yend='mass', colour='grouping'),
                      size=1) +
         scale_color_manual({'very_low': HORIZONTAL_COLOUR, 'low': AMBIGUOUS_COLOUR,
                             'very_high': HORIZONTAL_COLOUR, 'high': AMBIGUOUS_COLOUR,
                             'central': VERTICAL_COLOUR}, guide=False) +
         geom_line(aes(x='distance', y='smoothed_mass'), size=0.5) +
         geom_vline(xintercept=mean, colour='#000000', linetype='dotted', size=0.5) +
         geom_vline(xintercept=median, colour='#000000', linetype='dashed', size=0.5) +
         theme_bw() +
         labs(title=title, x='distance', y='probability mass'))

    if sqrt_distance:
        g += scale_x_sqrt(limits=(0, x_max))
    else:
        g += scale_x_continuous(limits=(0, x_max))
    if sqrt_mass:
        g += scale_y_sqrt(expand=(0, 0), limits=(0, y_max))
    else:
        g += scale_y_continuous(expand=(0, 0), limits=(0, y_max))

    return g.draw()


def distribution_plot_2(sample_name_a, sample_name_b, window_size, vertical_masses,
                        horizontal_masses, sqrt_distance, sqrt_mass):
    title = f'{sample_name_a} vs {sample_name_b} vertical vs horizontal distribution'
    mean = get_distance(vertical_masses, window_size, 'mean')
    median = get_distance(vertical_masses, window_size, 'median')
    max_distance = max(len(vertical_masses), len(horizontal_masses))
    x_max = max_distance / window_size
    y_max = 1.05 * max(max(vertical_masses), max(horizontal_masses))

    distances = [i / window_size for i in range(max_distance)]

    total_masses = [vertical_masses[i] + horizontal_masses[i] for i in range(max_distance)]

    df = pd.DataFrame(list(zip(distances, vertical_masses, horizontal_masses, total_masses)),
                      columns=['distance', 'vertical_mass', 'horizontal_mass', 'total_mass'])

    g = (ggplot(df) +
         geom_segment(aes(x='distance', xend='distance', y=0, yend='vertical_mass'),
                      size=1, colour=VERTICAL_COLOUR) +
         geom_segment(aes(x='distance', xend='distance', y='vertical_mass', yend='total_mass'),
                      size=1, colour=HORIZONTAL_COLOUR) +
         geom_vline(xintercept=mean, colour='#000000', linetype='dotted', size=0.5) +
         geom_vline(xintercept=median, colour='#000000', linetype='dashed', size=0.5) +
         theme_bw() +
         labs(title=title, x='distance', y='probability mass'))

    if sqrt_distance:
        g += scale_x_sqrt(limits=(0, x_max))
    else:
        g += scale_x_continuous(limits=(0, x_max))
    if sqrt_mass:
        g += scale_y_sqrt(expand=(0, 0), limits=(0, y_max))
    else:
        g += scale_y_continuous(expand=(0, 0), limits=(0, y_max))

    return g.draw()


def group_using_thresholds(masses, thresholds):
    """
    Assigns a group (very_low, low, central, high, very_high) to each mass, returned as a list.
    """
    grouping = []
    very_low, low = thresholds['very_low'], thresholds['low']
    very_high, high = thresholds['very_high'], thresholds['high']
    for i in range(len(masses)):
        if very_low is not None and i < very_low:
            grouping.append('very_low')
        elif low is not None and i < low:
            grouping.append('low')
        elif very_high is not None and i > very_high:
            grouping.append('very_high')
        elif high is not None and i > high:
            grouping.append('high')
        else:
            grouping.append('central')
    return grouping


def alignment_plot(sample_name_a, sample_name_b, alignments, window_size, sqrt_distance,
                   include_ambiguous=False):
    title = f'{sample_name_a} vs {sample_name_b} painted alignments'

    boundaries = [0]
    x_max = 0
    max_differences = 1
    for a in alignments:
        x_max += len(a.simplified_cigar)
        boundaries.append(x_max)
        max_differences = max(max_differences, a.get_max_differences())
    y_max = 1.05 * (max_differences / window_size)

    g = (ggplot() +
         theme_bw() +
         theme(panel_grid_major_x=element_blank(), panel_grid_minor_x=element_blank()) +
         scale_x_continuous(expand=(0, 0), limits=(0, x_max)) +
         labs(title=title, x='alignment position', y='distance'))

    if sqrt_distance:
        g += scale_y_sqrt(expand=(0, 0), limits=(0, y_max))
    else:
        g += scale_y_continuous(expand=(0, 0), limits=(0, y_max))

    for b in boundaries:
        g += geom_vline(xintercept=b, colour='#000000', size=0.5)

    offset = 0
    for a in alignments:
        for start, end in a.get_vertical_blocks(include_ambiguous):
            g += annotate('rect', xmin=start+offset, xmax=end+offset, ymin=0.0, ymax=y_max,
                          fill=VERTICAL_COLOUR, alpha=0.25)
        for start, end in a.get_horizontal_blocks(include_ambiguous):
            g += annotate('rect', xmin=start+offset, xmax=end+offset, ymin=0.0, ymax=y_max,
                          fill=HORIZONTAL_COLOUR, alpha=0.25)
        for start, end in a.get_ambiguous_blocks(include_ambiguous):
            g += annotate('rect', xmin=start+offset, xmax=end+offset, ymin=0.0, ymax=y_max,
                          fill=AMBIGUOUS_COLOUR, alpha=0.25)
        positions = [offset + ((w[0] + w[1]) / 2.0) for w in a.windows_no_overlap]
        distances = [d / window_size for d in a.window_differences]
        df = pd.DataFrame(list(zip(positions, distances)), columns=['pos', 'dist'])
        g += geom_line(data=df, mapping=aes(x='pos', y='dist'), size=0.5)
        offset += len(a.simplified_cigar)

    return g.draw()


def contig_plot(sample_name, painted, window_size, sqrt_distance):
    title = f'{sample_name} painted contigs'

    boundaries = [0]
    x_max = 0
    for name, contig in painted.contigs.items():
        x_max += contig.length
        boundaries.append(x_max)
    y_max = 1.05 * (max(1, painted.get_max_differences()) / window_size)

    g = (ggplot() +
         theme_bw() +
         theme(panel_grid_major_x=element_blank(), panel_grid_minor_x=element_blank()) +
         scale_x_continuous(expand=(0, 0), limits=(0, x_max)) +
         labs(title=title, x='contig position', y='distance'))

    if sqrt_distance:
        g += scale_y_sqrt(expand=(0, 0), limits=(0, y_max))
    else:
        g += scale_y_continuous(expand=(0, 0), limits=(0, y_max))

    for b in boundaries:
        g += geom_vline(xintercept=b, colour='#000000', size=0.5)

    offset = 0
    for name, contig in painted.contigs.items():
        for start, end in contig.get_vertical_blocks():
            g += annotate('rect', xmin=start+offset, xmax=end+offset, ymin=0.0, ymax=y_max,
                          fill=VERTICAL_COLOUR, alpha=0.25)
        for start, end in contig.get_horizontal_blocks():
            g += annotate('rect', xmin=start+offset, xmax=end+offset, ymin=0.0, ymax=y_max,
                          fill=HORIZONTAL_COLOUR, alpha=0.25)
        for points in contig.alignment_points:
            positions = [offset + p[0] for p in points]
            distances = [p[1] / window_size for p in points]
            df = pd.DataFrame(list(zip(positions, distances)), columns=['pos', 'dist'])
            g += geom_line(data=df, mapping=aes(x='pos', y='dist'), size=0.5)
        offset += contig.length

    return g.draw()
