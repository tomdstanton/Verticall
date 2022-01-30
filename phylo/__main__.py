#!/usr/bin/env python3
"""
Copyright 2022 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/XXXXXXXXX

This file is part of XXXXXXXXX. XXXXXXXXX is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. XXXXXXXXX is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with XXXXXXXXX.
If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import pathlib
import sys

from .shred import shred
from .help_formatter import MyParser, MyHelpFormatter
from .misc import check_python_version, get_ascii_art
from .log import bold
from .version import __version__


def main():
    check_python_version()
    args = parse_args(sys.argv[1:])

    if args.subparser_name == 'shred':
        check_shred_args(args)
        shred(args)


def parse_args(args):
    description = 'R|' + get_ascii_art() + '\n' + \
                  bold('XXXXXXXXX: a tool for generating recombination-free trees')
    parser = MyParser(description=description, formatter_class=MyHelpFormatter, add_help=False)

    subparsers = parser.add_subparsers(title='Commands', dest='subparser_name')
    shred_subparser(subparsers)

    longest_choice_name = max(len(c) for c in subparsers.choices)
    subparsers.help = 'R|'
    for choice, choice_parser in subparsers.choices.items():
        padding = ' ' * (longest_choice_name - len(choice))
        subparsers.help += choice + ': ' + padding
        d = choice_parser.description
        subparsers.help += d[0].lower() + d[1:]  # don't capitalise the first letter
        subparsers.help += '\n'

    help_args = parser.add_argument_group('Help')
    help_args.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                           help='Show this help message and exit')
    help_args.add_argument('--version', action='version', version='XXXXXXXXX v' + __version__,
                           help="Show program's version number and exit")

    # If no arguments were used, print the base-level help which lists possible commands.
    if len(args) == 0:
        parser.print_help(file=sys.stderr)
        sys.exit(1)

    return parser.parse_args(args)


def shred_subparser(subparsers):
    group = subparsers.add_parser('shred', description='break assemblies into pieces',
                                  formatter_class=MyHelpFormatter, add_help=False)

    required_args = group.add_argument_group('Required arguments')
    required_args.add_argument('-a', '--assemblies', type=str, required=True, nargs='+',
                               help='Input assemblies (FASTA or GFA format)')
    required_args.add_argument('-o', '--out_dir', type=pathlib.Path, required=True,
                               help='Output directory')

    setting_args = group.add_argument_group('Settings')
    setting_args.add_argument('--size', type=int, default=100,
                              help='Size of assembly pieces in bp')
    setting_args.add_argument('--overlap', type=int, default=50,
                              help='Overlap between assembly pieces in bp')

    other_args = group.add_argument_group('Other')
    other_args.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                            help='Show this help message and exit')
    other_args.add_argument('--version', action='version', version='XXXXXXXXX v' + __version__,
                            help="Show program's version number and exit")


def check_shred_args(args):
    pass


if __name__ == '__main__':
    main()
