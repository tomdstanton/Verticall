"""
This module contains code for the 'verticall mask' subcommand.

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

import sys

from .log import log, section_header, explanation, warning
from .misc import iterate_fasta, list_differences
from .tsv import get_column_index, check_header_for_assembly_a_regions, get_start_end


def mask(args):
    welcome_message(args)
    data, ref_name, ref_length, sample_names = load_regions(args.in_tsv, args.reference)
    sequences, sample_names = load_pseudo_alignment(args.in_alignment, ref_name, sample_names)
    masked_sequences = mask_sequences(data, sequences, ref_name, ref_length, sample_names,
                                      args.h_char, args.u_char)
    masked_sequences = finalise(masked_sequences, args.exclude_invariant)
    save_to_file(masked_sequences, args.out_alignment)
    finished_message()


def welcome_message(args):
    section_header('Starting Verticall mask')
    explanation('Verticall mask uses the results from Verticall pairwise to mask horizontal '
                'regions from a whole-genome pseudo-alignment.')
    log(f'Input pairwise tsv:      {args.in_tsv}')
    log(f'Input pseudo-alignment:  {args.in_alignment}')
    log(f'Output masked alignment: {args.out_alignment}')
    log()


def finished_message():
    section_header('Finished!')
    explanation('You can now use the masked pseudo-alignment to build a phylogeny using tools '
                'such as RAxML.')


def load_regions(filename, ref_name):
    section_header('Loading input data')
    log(f'{filename}:')
    ref_name, sample_names = check_tsv_file(filename, ref_name)
    data = {}
    v_col, h_col, u_col = None, None, None
    loaded_count, skipped_count = 0, 0
    with open(filename, 'rt') as pairwise_file:
        for i, line in enumerate(pairwise_file):
            parts = line.strip('\n').split('\t')
            if i == 0:
                v_col = get_column_index(parts, 'assembly_a_vertical_regions', filename)
                h_col = get_column_index(parts, 'assembly_a_horizontal_regions', filename)
                u_col = get_column_index(parts, 'assembly_a_unaligned_regions', filename)
            elif parts[0] == ref_name:
                if parts[0] == ref_name:
                    assembly_name = parts[1]
                    data[assembly_name] = load_regions_one_assembly(parts, v_col, h_col, u_col)
                    loaded_count += 1
                else:
                    skipped_count += 1
    if len(data) == 0:
        sys.exit(f'Error: no reference-to-assembly pairwise comparisons found in {filename} - is '
                 f'the provided reference name correct?')
    log(f'  {loaded_count} reference-to-assembly pairwise comparisons')
    ref_length = get_ref_length(data)
    log()
    return data, ref_name, ref_length, sample_names


def check_tsv_file(filename, ref_name):
    a_sample_names, all_sample_names = set(), set()

    with open(filename, 'rt') as f:
        for i, line in enumerate(f):
            parts = line.strip('\n').split('\t')
            if i == 0:  # header line
                check_header_for_assembly_a_regions(parts, filename)
            else:
                assembly_a, assembly_b = parts[0], parts[1]
                a_sample_names.add(assembly_a)
                all_sample_names.add(assembly_a)
                all_sample_names.add(assembly_b)

    if ref_name is None:  # user didn't specify a reference name
        if len(a_sample_names) == 1:
            ref_name = list(a_sample_names)[0]
            log(f'  Automatically determined reference name: {ref_name}')
        else:
            sys.exit('Error: could not automatically determine the reference name, please '
                     'specify one using the --reference option.')

    all_sample_names.discard(ref_name)
    return ref_name, sorted(all_sample_names)


def load_regions_one_assembly(parts, v_col, h_col, u_col):
    contig_names = set()

    vertical_regions = parts[v_col].split(',') if parts[v_col] else []
    contig_names |= {r.split(':')[0] for r in vertical_regions}
    vertical_regions = [get_start_end(r) for r in vertical_regions]

    horizontal_regions = parts[h_col].split(',') if parts[h_col] else []
    contig_names |= {r.split(':')[0] for r in horizontal_regions}
    horizontal_regions = [get_start_end(r) for r in horizontal_regions]

    unaligned_regions = parts[u_col].split(',') if parts[u_col] else []
    contig_names |= {r.split(':')[0] for r in unaligned_regions}
    unaligned_regions = [get_start_end(r) for r in unaligned_regions]

    if len(contig_names) > 1:
        contig_names_str = ', '.join(sorted(contig_names))
        sys.exit(f'Error: reference genome has more than one contig name ({contig_names_str})')

    # Double check that the data makes sense - the entire reference sequence should be covered once.
    all_regions = sorted(vertical_regions + horizontal_regions + unaligned_regions)
    for i, r in enumerate(all_regions):
        start, end = r
        if i > 0:
            prev_start, prev_end = all_regions[i-1]
            assert start == prev_end

    return vertical_regions, horizontal_regions, unaligned_regions


def get_ref_length(data):
    ref_lengths = set()
    for vertical_regions, horizontal_regions, unaligned_regions in data.values():
        ref_length = max(r[1] for r in vertical_regions + horizontal_regions + unaligned_regions)
        ref_lengths.add(ref_length)
    if len(ref_lengths) > 1:
        sys.exit('Error: multiple inconsistent reference sequence lengths')
    ref_length = list(ref_lengths)[0]
    log(f'  Reference length: {ref_length:,} bp')
    return ref_length


def load_pseudo_alignment(filename, ref_name, tsv_sample_names):
    alignment = {}
    log(f'{filename}:')
    sequence_names, sequence_lengths = set(), set()
    for name, seq in iterate_fasta(filename):
        sequence_names.add(name)
        sequence_lengths.add(len(seq))
        alignment[name] = seq

    if len(alignment) == 0:
        sys.exit(f'Error: no sequences could be loaded from {filename}')
    log(f'  {len(sequence_names)} sequences loaded')

    if len(sequence_lengths) != 1:
        sys.exit(f'Error: all sequences in {filename} must be the same length')
    sequence_length = list(sequence_lengths)[0]
    log(f'  Pseudo-alignment length: {sequence_length:,} bp')
    log()

    if ref_name not in sequence_names:
        sys.exit(f'Error: could not find reference sequence ({ref_name}) in {filename}')
    sequence_names.discard(ref_name)

    sequence_names = sorted(sequence_names)
    in_both, in_tsv_not_alignment, in_alignment_not_tsv = list_differences(tsv_sample_names,
                                                                           sequence_names)
    if len(in_both) == 0:
        sys.exit('Error: tsv and pseudo-alignment files have no sample names in common')
    if len(in_tsv_not_alignment) == 0 and len(in_alignment_not_tsv) == 0:
        log(f'All {len(in_both)} sample names match in tsv and pseudo-alignment files')
    else:
        log(f'{len(in_both)} sample names are common to both tsv and pseudo-alignment files')
    log()

    return alignment, in_both


def mask_sequences(data, sequences, ref_name, ref_length, sample_names, h_char, u_char):
    section_header('Masking sequences')
    ref_seq = sequences[ref_name]
    ref_pos_to_align_pos = get_alignment_positions(ref_seq, ref_length)
    longest_sample_name_len = max(len(s) for s in sample_names)
    masked_sequences = {ref_name: ref_seq}
    for sample_name in sample_names:
        log(f'{sample_name.rjust(longest_sample_name_len)}:', end=' ')
        masked_sequences[sample_name] = mask_one_sequence(data, sequences, sample_name, h_char,
                                                          u_char, ref_pos_to_align_pos, ref_length)
    log()
    return masked_sequences


def mask_one_sequence(data, sequences, sample_name, h_char, u_char, ref_pos_to_align_pos,
                      ref_length):
    _, horizontal_regions, unaligned_regions = data[sample_name]
    sample_seq = [b for b in sequences[sample_name]]
    unmasked, h_masked, u_masked = ref_length, 0, 0
    if h_char is not None:
        for start, end in horizontal_regions:
            unmasked -= (end - start)
            h_masked += (end - start)
            start, end = ref_pos_to_align_pos[start], ref_pos_to_align_pos[end]
            for i in range(start, end):
                sample_seq[i] = h_char
    if u_char is not None:
        for start, end in unaligned_regions:
            unmasked -= (end - start)
            u_masked += (end - start)
            start, end = ref_pos_to_align_pos[start], ref_pos_to_align_pos[end]
            for i in range(start, end):
                sample_seq[i] = u_char
    log_message = f'{100.0 * unmasked/ref_length:6.2f}% unmasked'
    if h_char is not None:
        log_message += f', {100.0 * h_masked/ref_length:5.2f}% "{h_char}"'
    if u_char is not None:
        log_message += f', {100.0 * u_masked/ref_length:5.2f}% "{u_char}"'
    log(log_message)
    return ''.join(sample_seq)


def get_alignment_positions(aligned_ref_seq, ref_length):
    """
    Returns a dictionary that translates reference positions to alignment positions. If the
    alignment contains no insertions in the reference sequence, these two sets of positions will be
    the same, but if there are insertions in the reference sequence, then the alignment positions
    can be bigger than the reference positions.
    """
    positions = {}
    ref_pos = 0
    for alignment_pos, base in enumerate(aligned_ref_seq):
        positions[ref_pos] = alignment_pos
        if base != '-':
            ref_pos += 1
    positions[ref_pos] = len(aligned_ref_seq)
    if ref_pos != ref_length:
        sys.exit('Error: length of reference sequence in alignment does not match length of '
                 'reference sequence in tsv file - have regions been masked with dashes?')
    return positions


def finalise(masked_sequences, exclude_invariant):
    section_header('Finalising sequences')
    masked_sequences = drop_empty_positions(masked_sequences)
    if exclude_invariant:
        masked_sequences = drop_invariant_positions(masked_sequences)
    log()
    return masked_sequences


def save_to_file(masked_sequences, filename):
    log(f'Saving masked pseudo-alignment to {filename}')
    with open(filename, 'wt') as f:
        for name, seq in masked_sequences.items():
            if len(seq) == 0:
                warning(f'excluded {name} due to empty sequence')
            else:
                f.write(f'>{name}\n{seq}\n')
    log()


def drop_empty_positions(sequences):
    """
    Returns an alignment where any columns that consist entirely of non-base characters are removed.
    """
    alignment_length = get_alignment_length(sequences)
    positions_to_remove = set()
    for i in range(alignment_length):
        bases_at_pos = {seq[i] for seq in sequences.values()}
        if 'A' not in bases_at_pos and 'C' not in bases_at_pos and 'G' not in bases_at_pos \
                and 'T' not in bases_at_pos:
            positions_to_remove.add(i)

    log(f'{len(positions_to_remove):,} empty positions '
        f'({100.0 * len(positions_to_remove)/alignment_length:.3}%) removed from pseudo-alignment')
    return drop_positions(sequences, positions_to_remove)


def drop_invariant_positions(sequences):
    """
    Returns an alignment where any columns that lack variation are removed.
    """
    alignment_length = get_alignment_length(sequences)
    positions_to_remove = set()
    for i in range(alignment_length):
        bases_at_pos = {seq[i] for seq in sequences.values()}
        if count_real_bases(bases_at_pos) < 2:
            positions_to_remove.add(i)

    log(f'{len(positions_to_remove):,} invariant positions '
        f'({100.0 * len(positions_to_remove)/alignment_length:.3}%) removed from pseudo-alignment')
    return drop_positions(sequences, positions_to_remove)


def get_alignment_length(sequences):
    alignment_lengths = {len(seq) for seq in sequences.values()}
    assert len(alignment_lengths) == 1
    return list(alignment_lengths)[0]


def drop_positions(sequences, positions_to_remove):
    if len(positions_to_remove) == 0:
        return sequences
    new_sequences = {}
    for name, seq in sequences.items():
        new_seq = ''.join(b for i, b in enumerate(seq) if i not in positions_to_remove)
        new_sequences[name] = new_seq
    return new_sequences


def count_real_bases(base_set):
    count = 0
    if 'A' in base_set:
        count += 1
    if 'C' in base_set:
        count += 1
    if 'G' in base_set:
        count += 1
    if 'T' in base_set:
        count += 1
    return count