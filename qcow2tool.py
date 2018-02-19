import argparse
import logging

parser = argparse.ArgumentParser(prog='qcow2tool')
parser.add_argument('-v', '--verbose', help='vebose', action='count', default=0)
parser.add_argument('-q', '--quiet', help='quiet', action='count', default=0)
subparsers = parser.add_subparsers()

import sub_chash

sub_chash.setup_subcmd(subparsers)

#import sub_squeeze
#
#sub_squeeze.setup_subcmd(subparsers)

import sub_analyze
sub_analyze.setup_subcmd(subparsers)


def main():
    args = parser.parse_args()
    volume = args.verbose - args.quiet
    if volume == 0:
        logging.basicConfig(level=logging.CRITICAL)
    elif volume == 1:
        logging.basicConfig(level=logging.WARNING)
    elif 2 <= volume:
        logging.basicConfig(level=logging.DEBUG)
    args.handler(args)


if __name__ == '__main__':
    main()
