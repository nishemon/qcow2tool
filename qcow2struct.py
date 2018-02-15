import io
from ctypes import *


class Header(BigEndianStructure):
    _fields_ = [
        ("magic", c_char * 4),
        ("version", c_uint32),
        ("backing_file_offset", c_uint64),
        ("backing_file_size", c_uint32),
        ("cluster_bits", c_uint32),
        ("size", c_uint64),
        ("crypt_method", c_uint32),
        ("l1_size", c_uint32),
        ("l1_table_offset", c_uint64),
        ("refcount_table_offset", c_uint64),
        ("refcount_table_clusters", c_uint32),
        ("nb_snapshots", c_uint32),
        ("snapshots_offset", c_uint64),
        # v3
        ("incompatible_features", c_uint64),
        ("compatible_features", c_uint64),
        ("refcount_order", c_uint32),
        ("header_length", c_uint32),
    ]


class HeaderExtensionHeader(BigEndianStructure):
    _fields_ = [
        ("type", c_uint32),
        ("size", c_uint32),
    ]


class BackingFileFormatName():
    def __init__(self, fileobj, size):
        self.name = fileobj.read(size)


class FeatureNameTableEntry(BigEndianStructure):
    _fields_ = [
        ("type", c_uint8),
        ("bit_number", c_uint8),
        ("name", c_char * 46),
    ]


class FeatureNameTable():
    def __init__(self, fileobj, size):
        entries = []
        while 0 < size:
            entry = FeatureNameTableEntry()
            fileobj.readinto(entry)
            entries.append(entry)
            size -= 48
        self.entries = entries


class BitmapsExtension(BigEndianStructure):
    _fields_ = [
        ("nb_bitmaps", c_uint32),
        ("reserved", c_uint32),
        ("bitmap_directory_size", c_uint64),
        ("bitmap_directory_offset", c_uint64),
    ]

    def __init__(self, fileobj, size):
        if size != 24:
            raise IOError, 'Unsupported Bitmaps'
        fileobj.readinto(self)


class FullDiskEncryptionHeaderPointer():
    extensions=[
        (0xE2792ACA, BackingFileFormatName),
        (0x6803f857, FeatureNameTable),
        (0x23852875, BitmapsExtension),
        (0x0537be77, FullDiskEncryptionHeaderPointer)
    ]


class RefcountTableEntry(BigEndianStructure):
    pass

class L1TableEntry(BigEndianStructure):
    _fields_ = [
        ("reserved1", c_uint64, 9),
        ("offset", c_uint64, 47),
        ("reserved2", c_uint64, 7),
        ("normal", c_uint64, 1),
    ]

    # revese?
class L2TableEntry(BigEndianStructure):
    _fields_ = [
        ("normal", c_uint64, 1),
        ("compressed", c_uint64, 1),
        ("descriptor", c_uint64, 62),
    ]
