import argparse


def shrink(conf, args):
    pass


def setup_subcmd(subparsers):
    shrink_parser = subparsers.add_parser('shrink', help='shrink qcow2 image')
    shrink_parser.add_argument('src', type=argparse.FileType('r'), nargs=1)
    shrink_parser.add_argument('dest', type=argparse.FileType('w'), nargs=1)
    shrink_parser.add_argument('-z', '--zopfli', help='compress with zopfli')
    shrink_parser.add_argument('-s', '--shallow', help='keep backing files')
    shrink_parser.add_argument('-x', '--exclude', nargs='+', type=argparse.FileType('r'),
                               help='erase unreference areas')
    shrink_parser.add_argument('-c', '--common', nargs='+', type=argparse.FileType('r'), help='collect common areas')
    shrink_parser.set_defaults(handler=shrink)
