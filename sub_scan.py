import argparse


def scan(conf, args):
    pass

def setup_subcmd(subparsers):
    scan_parser = subparsers.add_parser('scan', help='scan qcow2 image dir')
    scan_parser.add_argument('srcdir', type=argparse.FileType('r'), nargs=1)
    scan_parser.set_defaults(handler=scan)
