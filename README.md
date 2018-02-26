# qcow2tool
A tool for tweak qcow2 file

## squeeze
compress qcow2 file
- You can compress a snapshot file without the backing file. 

```
python qcow2tool.py squeeze (src) (dest)
```

## warining
This is a toy tool. I have not done enough testing.
So, you shuld check output files with "qemu-img compare".

## status
- not support to internal snapshot, bitmaps and header extensions

