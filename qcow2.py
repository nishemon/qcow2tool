import io
from ctypes import *
from qcow2struct import *


def load_table(fileobj, table_offset, size, entryType):
    tent = entryType()
    fileobj.seek(table_offset)
    self.fileobj.readinto(tent)


class Qcow2File(io.BufferedIOBase):
    def __init__(self, filename, backing=True):
        fileobj = open(filename, 'rb')
        header = Header()
        fileobj.readinto(header)
        if header.magic != 'QFI\xfb':
            raise IOError, 'Not QCOW2 format'
        if header.version == 2:
            header.incompatible_fefatures = 0
            header.compatible_features = 0
            header.refcount_order = 4
            header.header_length = 72
            fileobj.seek(72)
        elif header.version != 3:
            raise IOError, 'Unsupported version {}' % header.version
        while True:
            ext = HeaderExtensionHeader()
            fileobj.readinto(ext)
            if ext.type == 0:
                break

        self.header = header
        self.fileobj = fileobj
        self.backingFile = None
        self.backingFile = self.getBackingFile()
        self.backing = Qcow2File(self.backingFile) if backing and self.backingFile else None
        cluster_size = 1 << header.cluster_bits
        self.refcounts = load_table(fileobj, header.refcount_table_offset,
                                   header.refcount_table_clusters * cluster_size, RefcountTableEntry)
        self.l1 = load_table(fileobj, header.l1_table_offset, header.l1_size, L1TableEntry)

    def readRefcountList(self, offset):
        entries = 1 << (self.header.cluster_bits - (self.header.refcount_order - 3))
        iCluster = offset >> self.header.cluster_bits
        t = self.refcounts[iCluster / entries]
        if t.reserved != 0:
            raise IOError, 'Unsupported Refcount table entry'
        if t.block_offset == 0:
            return [0] * entries
        self.fileobj.seek(t.block_offset)
        self.fileobj.read(1 << self.header.cluster_bits)

    def readL2List(self, offset):
        ent = L2TableEntry()
        self.fileobj.readinto(ent)
        if ent.compressed:
            x = 62 - (self.header.cluster_bits - 8)
            foff = ent.descriptor & ((1 << x) - 1)
            sectors = ent.descriptor >> x
            Cluster(foff, sectors * 512, True)
        else:
            if ent.descriptor & 1:
                foff = ent.descriptor >> 9
                if (1 << 47) <= foff or ent.descriptor & 0x1E:
                    raise IOError, 'Unknown L2 entry format'
            else:
                Cluster(foff, zero=True)

    def getBackingFile(self):
        off = self.header.backing_file_offset
        if off == 0:
            return None
        if self.backingFile:
            return self.backingFile
        self.fileobj.seek(off)
        return self.fileobj.read(self.header.backing_file_size)

    def close(self):
        self.backing.close()
        self.fileobj.close()

    def read(self, size=-1):
        pass

    def getHeader(self):
        return self.header
