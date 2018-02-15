import argparse

parser = argparse.ArgumentParser(prog='qcow2tool')
subparsers = parser.add_subparsers()

import sub_chash

sub_chash.setup_subcmd(subparsers)

import sub_shrink

sub_shrink.setup_subcmd(subparsers)


def main():
    pass
