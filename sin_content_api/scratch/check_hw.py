import ctypes
import os

free_bytes = ctypes.c_ulonglong()
total_bytes = ctypes.c_ulonglong()
ctypes.windll.kernel32.GetDiskFreeSpaceExW('C:\\', None, ctypes.byref(total_bytes), ctypes.byref(free_bytes))
print('Disk_Total_GB: %.2f' % (total_bytes.value / (1024**3)))
print('Disk_Free_GB: %.2f' % (free_bytes.value / (1024**3)))

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ('dwLength', ctypes.c_ulong),
        ('dwMemoryLoad', ctypes.c_ulong),
        ('ullTotalPhys', ctypes.c_ulonglong),
        ('ullAvailPhys', ctypes.c_ulonglong),
        ('ullTotalPageFile', ctypes.c_ulonglong),
        ('ullAvailPageFile', ctypes.c_ulonglong),
        ('ullTotalVirtual', ctypes.c_ulonglong),
        ('ullAvailVirtual', ctypes.c_ulonglong),
        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
    ]

stat = MEMORYSTATUSEX()
stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
print('RAM_Total_GB: %.2f' % (stat.ullTotalPhys / (1024**3)))
print('RAM_Avail_GB: %.2f' % (stat.ullAvailPhys / (1024**3)))
print('CPU_Count: %d' % (os.cpu_count() or 1))
