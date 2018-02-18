import io
from ctypes import *


class Header(BigEndianStructure):
    """from qcow2.h: QcowHeader"""
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
        ("autoclear_feature", c_uint64),
        ("refcount_order", c_uint32),
        ("header_length", c_uint32),
    ]


class SnapshotHeader(BigEndianStructure):
    """from qcow2.h: QcowSnapshotHeader"""
    _fields_ = [
        ("l1_table_offset", c_uint64),
        ("l1_size", c_uint32),
        ("id_str_size", c_uint16),
        ("name_size", c_uint16),
        ("date_sec", c_uint32),
        ("date_nsec", c_uint32),
        ("vm_clock_nsec", c_uint64),
        ("vm_state_size", c_uint32),
        ("extra_data_size", c_uint32),
    ]


class SnapshotExtraData(BigEndianStructure):
    """from qcow2.h: QcowSnapshotExtraData"""
    _fields_ = [
        ("vm_state_size_large", c_uint64),
        ("disk_size", c_uint64),
    ]


class HeaderExtensionHeader(BigEndianStructure):
    """from qcow2.h: Qcow2UnknownHeaderExtension"""
    _fields_ = [
        ("magic", c_uint32),
        ("len", c_uint32),
    ]


class FeatureNameTableEntry(BigEndianStructure):
    """from qcow2.h: Qcow2Feature"""
    _fields_ = [
        ("type", c_uint8),
        ("bit", c_uint8),
        ("name", c_char * 46),
    ]


class BitmapsExtension(BigEndianStructure):
    """from qcow2.h: Qcow2BitmapHeaderExt"""
    _fields_ = [
        ("nb_bitmaps", c_uint32),
        ("reserved", c_uint32),
        ("bitmap_directory_size", c_uint64),
        ("bitmap_directory_offset", c_uint64),
    ]


class FullDiskEncryptionHeaderPointer(BigEndianStructure):
    """from qcow2.h: Qcow2CryptoHeaderExtension"""
    _fields_ = [
        ("offset", c_uint64),
        ("length", c_uint64),
    ]


class RefcountTableEntry(BigEndianStructure):
    _fields_ = [
        ("offset", c_uint64),
    ]


class L1TableEntry(BigEndianStructure):
    _fields_ = [
        ("normal", c_uint64, 1),
        ("reserved", c_uint64, 7),
        ("offset", c_uint64, 56),
    ]



# reverse?
class L2TableEntry(BigEndianStructure):
    _fields_ = [
        ("normal", c_uint64, 1),
        ("compressed", c_uint64, 1),
        ("descriptor", c_uint64, 62),
    ]
