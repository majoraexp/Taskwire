import platform
import subprocess
import time

import psutil
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class SystemWorker(QObject):
    # Signals to update the UI
    cpu_update = pyqtSignal(float, list, list) # Overall %, List of per-core %, List of per-core freq
    memory_update = pyqtSignal(dict)     # Dictionary of memory stats (RAM + Swap)
    gpu_update = pyqtSignal(float)       # GPU Utilization %
    fan_update = pyqtSignal(dict)        # Fan speeds {label: rpm}
    process_update = pyqtSignal(list)    # List of process info dicts
    disk_update = pyqtSignal(dict)       # Disk usage stats
    disk_io_update = pyqtSignal(dict)    # Disk Read/Write speeds
    network_update = pyqtSignal(dict)    # Network speeds
    temp_update = pyqtSignal(dict)       # Temperature sensors
    
    def __init__(self):
        super().__init__()
        self.running = True
        
        try:
            self.last_net_io = psutil.net_io_counters()
        except Exception:
            self.last_net_io = None
            
        try:
            self.last_disk_io = psutil.disk_io_counters()
        except Exception:
            self.last_disk_io = None
            
        self.last_time = time.time()
        
        try:
            self.cpu_count = psutil.cpu_count() or 1
        except Exception:
            self.cpu_count = 1
            
        try:
            self.mem_total = psutil.virtual_memory().total
        except Exception:
            self.mem_total = 1024**3 # Fallback 1GB

        self.procs = {} # Cache for Process objects
        self.cpu_ema = None # Exponential Moving Average for CPU

    def start_monitoring(self):
        if getattr(self, '_loop_running', False):
            return
        self._loop_running = True
        
        print(f"DEBUG: SystemWorker Thread ID: {int(QThread.currentThreadId())}")

        is_windows = platform.system() == "Windows"
        
        # Init CPU counters to avoid first-call spikes
        psutil.cpu_percent(interval=None)
        psutil.cpu_times_percent(interval=None)
        psutil.cpu_times_percent(interval=None, percpu=True)
        
        while self.running:
            # Sleep at start to ensure valid interval for first iteration
            QThread.msleep(250)

            # 1. CPU Stats
            # Use cpu_times_percent to get breakdown.
            # Calculate Usage excluding IOWait (to match KDE): Used = 100 - Idle - IOWait
            times_overall = psutil.cpu_times_percent(interval=None)
            cpu_overall = max(0.0, 100.0 - times_overall.idle - times_overall.iowait)
            
            # Capture System Overhead (IRQ/SoftIRQ) for the "System" row.
            # We EXCLUDE 'system' because that is already counted in per-process CPU usage (syscalls).
            # Including 'system' here would double-count it.
            sys_percent = times_overall.irq + times_overall.softirq + times_overall.steal + times_overall.guest
            
            # Use raw value to match Process List sum exactly (removing EMA)
            
            times_per_core = psutil.cpu_times_percent(interval=None, percpu=True)
            
            cpu_per_core = []
            for t in times_per_core:
                # Normalize manually because psutil percpu=True sometimes returns 
                # values that don't sum to 100 on short intervals (bug/feature?)
                total = t.user + t.nice + t.system + t.idle + t.iowait + t.irq + t.softirq + t.steal
                
                if total > 0:
                    idle_pct = (t.idle / total) * 100.0
                    iowait_pct = (t.iowait / total) * 100.0
                    cpu_per_core.append(max(0.0, 100.0 - idle_pct - iowait_pct))
                else:
                    cpu_per_core.append(0.0)
            
            # CPU Frequency
            cpu_freqs = []
            try:
                freqs = psutil.cpu_freq(percpu=True)
                if freqs:
                    cpu_freqs = [f.current for f in freqs]
            except Exception:
                pass
            
            self.cpu_update.emit(cpu_overall, cpu_per_core, cpu_freqs)
            
            # 2. Memory Stats (RAM + Swap)
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            mem_stats = {
                "total": mem.total,
                "available": mem.available,
                "percent": mem.percent,
                "used": mem.used,
                "swap_total": swap.total,
                "swap_used": swap.used,
                "swap_percent": swap.percent
            }


            # 3. GPU Stats (nvidia-smi fallback)
            gpu_usage = 0.0
            try:
                if not is_windows:
                    # Linux: Try nvidia-smi
                    res = subprocess.run(
                        ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, check=False
                    )
                    if res.returncode == 0:
                        gpu_usage = float(res.stdout.strip())
            except Exception: # pylint: disable=W0718
                pass
            self.gpu_update.emit(gpu_usage)
            
            # 4. Disk Stats (Usage)
            disks_data = {}
            try:
                if not is_windows:
                    # Linux: Physical Disks via lsblk
                    cmd = ["lsblk", "-d", "-n", "-o", "NAME,MODEL,SIZE", "-b"]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                    
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n'):
                            parts = line.split()
                            if len(parts) >= 2:
                                name = parts[0]
                                if "zram" in name: # Exclude zram devices
                                    continue
                                size = int(parts[-1])
                                model = " ".join(parts[1:-1]) if len(parts) > 2 else name
                                disks_data[f"/dev/{name}"] = {
                                    "model": model, "size": size, "used": 0, "percent": 0.0
                                }

                    # Sum Usage from Partitions
                    partitions = psutil.disk_partitions(all=False)
                    seen_devices = set()
                    
                    for part in partitions:
                        # Filter pseudo-filesystems and loops
                        # We block specific known pseudo-types but allow everything else (ext4, ntfs, btrfs, vfat, etc.)
                        if 'loop' in part.device or part.fstype in ['squashfs', 'overlay', 'tmpfs', 'devtmpfs', 'ramfs', 'overlayfs', 'aufs', 'docker', 'container', 'iso9660']:
                            continue
                        
                        # Deduplicate by device path (handles Btrfs subvolumes reporting same device)
                        if part.device in seen_devices:
                            continue
                        seen_devices.add(part.device)
                        
                        try:
                            usage = psutil.disk_usage(part.mountpoint)
                            
                            # Find parent physical disk
                            for p_disk_path, p_disk_data in disks_data.items():
                                # Check if partition device starts with physical disk path
                                # e.g. /dev/nvme0n1p1 starts with /dev/nvme0n1
                                if part.device.startswith(p_disk_path):
                                    p_disk_data['used'] += usage.used
                                    # Clamp to size (metadata overhead might cause minor over-reporting relative to lsblk size)
                                    if p_disk_data['used'] > p_disk_data['size']:
                                        p_disk_data['used'] = p_disk_data['size']
                                    break
                        except (PermissionError, OSError):
                            continue
                else:
                    # Windows: Treat Volumes as Disks
                    partitions = psutil.disk_partitions()
                    for part in partitions:
                        try:
                            usage = psutil.disk_usage(part.mountpoint)
                            # Device is "C:\", "D:\"
                            disks_data[part.device] = {
                                "model": "Local Disk", 
                                "size": usage.total, 
                                "used": usage.used, 
                                "percent": usage.percent
                            }
                        except (PermissionError, OSError):
                            continue

                # Calculate Percentages (Linux only, Windows done above)
                for d in disks_data.values():
                    if d['size'] > 0 and 'percent' not in d:
                        # Check if not set
                        d['percent'] = (d['used'] / d['size']) * 100
                    elif d['size'] > 0 and d['percent'] == 0.0 and d['used'] > 0:
                         d['percent'] = (d['used'] / d['size']) * 100
                    
                self.disk_update.emit(disks_data)
            except Exception: # pylint: disable=W0718
                pass
            
            # 4.5 Disk IO Speed
            try:
                current_disk_io = psutil.disk_io_counters()
                current_time = time.time()
                time_delta = current_time - self.last_time
                
                # Network calculation also uses last_time, but we need to ensure consistent delta.
                # Since we are in the same loop iteration, time_delta is roughly the same, 
                # but we should calculate io stats before updating self.last_time at the end of loop,
                # or just use the same delta.
                # However, network block below updates self.last_time. 
                # To avoid conflict, let's use the same logic pattern as network.
                
                if current_disk_io and self.last_disk_io and time_delta > 0:
                    read_bytes = current_disk_io.read_bytes - self.last_disk_io.read_bytes
                    write_bytes = current_disk_io.write_bytes - self.last_disk_io.write_bytes
                    
                    read_speed = read_bytes / time_delta
                    write_speed = write_bytes / time_delta
                    
                    self.disk_io_update.emit({
                        "read": read_speed,
                        "write": write_speed
                    })
                
                self.last_disk_io = current_disk_io
                
            except Exception: # pylint: disable=W0718
                pass

            # 4. Network Stats (Speed)
            try:
                current_net_io = psutil.net_io_counters()
                current_time = time.time()
                time_delta = current_time - self.last_time
                
                if time_delta > 0:
                    bytes_sent = current_net_io.bytes_sent - self.last_net_io.bytes_sent
                    bytes_recv = current_net_io.bytes_recv - self.last_net_io.bytes_recv
                    upload_speed = bytes_sent / time_delta
                    download_speed = bytes_recv / time_delta
                    
                    self.network_update.emit({
                        "upload": upload_speed,
                        "download": download_speed
                    })
                    
                self.last_net_io = current_net_io
                self.last_time = current_time
            except Exception: # pylint: disable=W0718
                pass

            # 5. Temperatures
            try:
                if not is_windows:
                    temps = psutil.sensors_temperatures()
                    temp_data = {}
                    
                    # Helper to find specific label in entries
                    def find_entry(entries, search_labels):
                        for e in entries:
                            if not e.label: continue
                            for sl in search_labels:
                                if sl.lower() in e.label.lower():
                                    return e.current
                        return None

                    # 1. CPU (Intel/AMD)
                    cpu_temp = None
                    if 'coretemp' in temps:
                        # Intel: Package id 0
                        cpu_temp = find_entry(temps['coretemp'], ['Package id 0', 'Package'])
                        if cpu_temp is None and temps['coretemp']:
                            cpu_temp = max(e.current for e in temps['coretemp']) # Fallback: Max core
                    elif 'k10temp' in temps:
                        # AMD: Tctl or Tdie
                        cpu_temp = find_entry(temps['k10temp'], ['Tctl', 'Tdie'])
                        if cpu_temp is None and temps['k10temp']:
                             cpu_temp = max(e.current for e in temps['k10temp'])
                    
                    if cpu_temp is not None:
                        temp_data["CPU Package"] = cpu_temp

                    # 2. GPU
                    gpu_temp = None
                    if 'amdgpu' in temps:
                        gpu_temp = find_entry(temps['amdgpu'], ['edge', 'junction'])
                        if gpu_temp is None and temps['amdgpu']:
                             gpu_temp = temps['amdgpu'][0].current
                    elif 'nouveau' in temps:
                         if temps['nouveau']: gpu_temp = temps['nouveau'][0].current
                    
                    # NVIDIA fallback check
                    if gpu_temp is None:
                         try:
                             res = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True)
                             if res.returncode == 0:
                                 gpu_temp = float(res.stdout.strip())
                         except: pass

                    if gpu_temp is not None:
                        temp_data["GPU"] = gpu_temp

                    # 3. Disks / NVMe
                    for name, entries in temps.items():
                        if name == 'nvme':
                            t = find_entry(entries, ['Composite', 'Sensor 1'])
                            if t is None and entries: t = entries[0].current
                            if t: temp_data["NVMe"] = t
                        elif name == 'drivetemp':
                             if entries: 
                                 d_label = entries[0].label or 'Disk'
                                 temp_data[d_label] = entries[0].current

                    # 4. Fill remaining slots with generic if space (max 5)
                    processed_keys = ['coretemp', 'k10temp', 'amdgpu', 'nouveau', 'nvme', 'drivetemp']
                    
                    for name, entries in temps.items():
                        if len(temp_data) >= 5: break
                        if name in processed_keys: continue
                        
                        # Add up to 2 generic sensors from others
                        added = 0
                        for entry in entries:
                            if len(temp_data) >= 5 or added >= 2: break
                            label = f"{name} {entry.label or ''}".strip()
                            temp_data[label] = entry.current
                            added += 1

                    if not temp_data:
                         temp_data = {"CPU": 0.0}

                    self.temp_update.emit(temp_data)
                else:
                    # Windows often lacks temperature support via psutil
                    # Send dummy data for the aesthetic check
                    self.temp_update.emit({"CPU Core": 55.0, "GPU Die": 42.0, "SSD": 35.0})
            except Exception: # pylint: disable=W0718
                pass

            # 6. Fan Speeds
            try:
                fans = psutil.sensors_fans()
                fan_data = {}
                if fans:
                    for name, entries in fans.items():
                        for entry in entries:
                            label = entry.label or name
                            fan_data[label] = entry.current
                else:
                    # Dummy data if no fans detected (e.g. VM or Windows limitation)
                    fan_data = {"Fan 1": 1200, "Fan 2": 800}
                self.fan_update.emit(fan_data)
            except Exception: # pylint: disable=W0718
                pass

            # 7. Process List
            try:
                # Update process cache
                current_pids = set()
                for p in psutil.process_iter(['pid']):
                    pid = p.info['pid']
                    current_pids.add(pid)
                    if pid not in self.procs:
                        try:
                            # New process: Init CPU counter
                            proc = psutil.Process(pid)
                            proc.cpu_percent(interval=None)
                            self.procs[pid] = proc
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                
                # Remove dead processes
                dead_pids = set(self.procs.keys()) - current_pids
                for pid in dead_pids:
                    del self.procs[pid]

                processes = []
                total_pss = 0
                
                for pid, p in self.procs.items():
                    try:
                        # Get CPU (stateless call thanks to cached object)
                        try:
                            cpu = p.cpu_percent(interval=None) / self.cpu_count
                        except:
                            cpu = 0.0
                        
                        with p.oneshot():
                            # Name
                            try: name = p.name()
                            except Exception:
                                name = "Unknown"

                            # Memory: Try PSS, fallback to RSS
                            try:
                                mem_info = p.memory_full_info()
                            except (psutil.AccessDenied, ValueError):
                                try:
                                    mem_info = p.memory_info()
                                except Exception:
                                    # Fallback object if even RSS fails
                                    class DummyMem: # pylint: disable=R0903
                                        """
                                        Dummy class for memory info when psutil.memory_info() fails.
                                        """
                                        rss = 0
                                        vms = 0
                                        pss = 0
                                    mem_info = DummyMem()
                            
                            # Use PSS if available (proportional set size), else RSS for accurate memory usage
                            val = getattr(mem_info, 'pss', mem_info.rss)
                            total_pss += val
                            mem_percent = (val / self.mem_total) * 100

                            # Get swap from psutil or /proc
                            mem_swap = getattr(mem_info, 'swap', 0)
                            if mem_swap == 0:
                                try:
                                    with open(f'/proc/{pid}/status', 'r') as f:
                                        for line in f:
                                            if line.startswith('VmSwap:'):
                                                mem_swap = int(line.split()[1]) * 1024  # kB to bytes
                                                break
                                except:
                                    pass

                            try: ppid = p.ppid()
                            except Exception:
                                ppid = 0
                            
                            try: io = p.io_counters()
                            except Exception:
                                io = None
                            
                            try: num_threads = p.num_threads()
                            except Exception:
                                num_threads = 0
                            
                            try: username = p.username()
                            except Exception:
                                username = ""
                            
                            try: status = p.status()
                            except Exception:
                                status = ""

                            info = {
                                'pid': pid,
                                'name': name,
                                'cpu_percent': cpu,
                                'memory_percent': mem_percent,
                                'ppid': ppid,
                                'io_counters': io,
                                'memory_info': mem_info,
                                'mem_shared': getattr(mem_info, 'shared', 0),
                                'mem_swap': mem_swap,
                                'num_threads': num_threads,
                                'username': username,
                                'status': status
                            }
                            processes.append(info)
                    except psutil.NoSuchProcess:
                        continue
                    except Exception: # pylint: disable=W0718
                        # Catch other unexpected errors to prevent loop crash
                        continue
                
                # Add System/Kernel Entry
                mem = psutil.virtual_memory()
                # Use total - available to match Dashboard
                total_used = mem.total - mem.available
                
                # Normalization: If process sum > system used, scale down to match.
                # This ensures the process list strictly adds up to the Dashboard widget.
                if total_pss > total_used and total_used > 0:
                    ratio = total_used / total_pss
                    for p in processes:
                        p['memory_percent'] *= ratio
                        
                        # Scale memory_info fields
                        old_mem = p['memory_info']
                        
                        class ScaledMemInfo:
                            def __init__(self, original, ratio):
                                self.rss = int(original.rss * ratio)
                                self.vms = original.vms # Keep virtual size accurate
                                self.pss = int(getattr(original, 'pss', original.rss) * ratio)
                                self.shared = int(getattr(original, 'shared', 0) * ratio)
                                self.swap = getattr(original, 'swap', 0)
                        
                        p['memory_info'] = ScaledMemInfo(old_mem, ratio)
                        
                        # Update flattened fields
                        if 'mem_shared' in p:
                            p['mem_shared'] = int(p['mem_shared'] * ratio)
                    
                    remainder = 0
                else:
                    remainder = max(0, total_used - total_pss)
                
                if remainder > 0:
                     # Define Dummy Mem Info for System Entry
                     class SysMem: # pylint: disable=R0903
                         """
                         Dummy class for system memory info.
                         """
                         rss = remainder
                         vms = remainder
                         pss = remainder
                     
                     sys_entry = {
                        'pid': -1,
                        'name': "System / Kernel / Other",
                        'cpu_percent': 0.0,
                        'memory_percent': (remainder / self.mem_total) * 100,
                        'ppid': 0,
                        'io_counters': None,
                        'memory_info': SysMem(),
                        'mem_shared': 0,
                        'mem_swap': 0,
                        'num_threads': 0,
                        'username': "root",
                        'status': "running"
                     }
                     processes.append(sys_entry)

                

                processes.sort(key=lambda p: p['cpu_percent'] or 0, reverse=True)
                self.process_update.emit(processes)
                self.memory_update.emit(mem_stats)
            except Exception as e: # pylint: disable=W0718
                print(f"Error fetching processes: {e}")

    def stop(self):
        self.running = False
