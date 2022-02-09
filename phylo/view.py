"""
Copyright 2022 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/XXXXXXXXX

This file is part of XXXXXXXXX. XXXXXXXXX is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. XXXXXXXXX is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with XXXXXXXXX.
If not, see <https://www.gnu.org/licenses/>.
"""

import pandas as pd
from plotnine import ggplot, aes, geom_segment, geom_vline, labs, theme_bw, \
    scale_y_continuous, scale_y_sqrt
import sys

from .distance import get_mean_distance, get_median_distance, get_median_int_distance


def view(args):
    piece_size, aligned_frac, masses = \
        load_distance_distribution(args.alignment_results, args.assembly_1, args.assembly_2)

    distances = [i / piece_size for i in range(len(masses))]
    df = pd.DataFrame(list(zip(distances, masses)),  columns=['distance', 'mass'])
    title = f'{args.assembly_1} vs {args.assembly_2}'
    mean = get_mean_distance(masses, piece_size)
    median = get_median_distance(masses, piece_size)
    median_int = get_median_int_distance(masses, piece_size)

    g = (ggplot(df, aes('distance', 'mass')) +
         geom_segment(aes(x='distance', xend='distance', y=0, yend='mass'), colour='#880000') +
         geom_vline(xintercept=mean, colour='#008888', linetype='dotted') +
         geom_vline(xintercept=median, colour='#0000bb', linetype='dotted') +
         geom_vline(xintercept=median_int, colour='#00bb00', linetype='dotted') +
         theme_bw() +
         labs(title=title))

    y_max = 1.05 * max(masses)
    if args.sqrt_y:
        g += scale_y_sqrt(expand=(0, 0), limits=(0, y_max))
    else:
        g += scale_y_continuous(expand=(0, 0), limits=(0, y_max))

    print(g)


def load_distance_distribution(alignment_results, assembly_1, assembly_2):
    with open(alignment_results, 'rt') as results:
        for line in results:
            parts = line.strip().split('\t')
            if parts[0] == assembly_1 and parts[1] == assembly_2:
                piece_size = int(parts[2])
                aligned_frac = float(parts[3])
                masses = [float(p) for p in parts[4:]]
                return piece_size, aligned_frac, masses
    sys.exit(f'\nError: could not find {assembly_1} and {assembly_2} in {alignment_results}')
