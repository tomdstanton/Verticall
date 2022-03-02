"""
Copyright 2022 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/XXXXXXXXX

This module contains code related to 'painting' an assembly using the alignments and the high/low
identity thresholds.

This file is part of XXXXXXXXX. XXXXXXXXX is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. XXXXXXXXX is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with XXXXXXXXX.
If not, see <https://www.gnu.org/licenses/>.
"""

from .alignment import remove_indels, compress_indels, swap_insertions_and_deletions, \
    cigar_to_contig_positions
from .distance import get_difference_count
from .misc import iterate_fasta


def paint_assemblies(args, name_a, name_b, filename_a, filename_b, alignments, window_size,
                     low, high):
    log_text = [f'  painting {name_a}']
    painted_a = PaintedAssembly(filename_a)
    painted_b = PaintedAssembly(filename_b)

    for a in alignments:
        painted_a.add_alignment(a, 'query', window_size, args.ignore_indels)
        painted_b.add_alignment(a, 'target', window_size, args.ignore_indels)

    return painted_a, painted_b, log_text


class PaintedAssembly(object):

    def __init__(self, fasta_filename):
        self.contigs = {}
        for name, seq in iterate_fasta(fasta_filename):
            self.contigs[name] = PaintedContig(seq)

    def add_alignment(self, a, assembly_status, window_size, ignore_indels):
        if assembly_status == 'query':
            name, start, end = a.query_name, a.query_start, a.query_end
            cigar = a.expanded_cigar
        elif assembly_status == 'target':
            name, start, end = a.target_name, a.target_start, a.target_end
            cigar = swap_insertions_and_deletions(a.expanded_cigar)
        else:
            assert False
        self.contigs[name].add_alignment(start, end, cigar, window_size, ignore_indels)


class PaintedContig(object):

    def __init__(self, seq):
        self.length = len(seq)
        self.window_differences = []   # (contig position, difference count)

    def add_alignment(self, a_start, a_end, cigar, window_size, ignore_indels):
        assert window_size % 100 == 0
        window_step = window_size // 100
        cigar_to_contig = cigar_to_contig_positions(cigar, a_start, a_end)
        if ignore_indels:
            cigar, cigar_to_contig = remove_indels(cigar, cigar_to_contig)
        else:
            cigar, cigar_to_contig = compress_indels(cigar, cigar_to_contig)

        start, end = 0, window_size
        while end <= len(cigar):
            cigar_window = cigar[start:end]
            assert len(cigar_window) == window_size
            difference_count = get_difference_count(cigar_window)
            contig_pos = (cigar_to_contig[start] + cigar_to_contig[end-1]) // 2
            self.window_differences.append((contig_pos, difference_count))
            start += window_step
            end += window_step
