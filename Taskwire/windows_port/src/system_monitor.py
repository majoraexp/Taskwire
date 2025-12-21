import platform
import subprocess
import time
import psutil
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class SystemWorker(QObject):
    # Signals to update the UI
    cpu_update = pyqtSignal(float, list) 
    memory_update = pyqtSignal(dict)     
    gpu_update = pyqtSignal(float)       
    fan_update = pyqtSignal(dict)        
    process_update = pyqtSignal(list)    
    disk_update = pyqtSignal(dict)       
    disk_io_update = pyqtSignal(dict)    
    network_update = pyqtSignal(dict)    
    temp_update = pyqtSignal(dict)       
    
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
        self.cpu_count = psutil.cpu_count() or 1
        self.mem_total = psutil.virtual_memory().total
        self.procs = {} 

    def start_monitoring(self):
        if getattr(self, '_loop_running', False):
            return
        self._loop_running = True

        # Init CPU counters
        psutil.cpu_percent(interval=None)
        psutil.cpu_times_percent(interval=None)
        psutil.cpu_times_percent(interval=None, percpu=True)
        
        while self.running:
            QThread.msleep(1000)

            # 1. CPU Stats (Windows Compatible)
            try:
                # Windows times: user, system, idle, interrupt, dpc
                times_overall = psutil.cpu_times_percent(interval=None)
                # Used = 100 - Idle
                cpu_overall = max(0.0, 100.0 - times_overall.idle)
                
                # Per Core
                times_per_core = psutil.cpu_times_percent(interval=None, percpu=True)
                cpu_per_core = [max(0.0, 100.0 - t.idle) for t in times_per_core]
                
                self.cpu_update.emit(cpu_overall, cpu_per_core)
            except Exception:
                self.cpu_update.emit(0.0, [])

            # 2. Memory Stats
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
            self.memory_update.emit(mem_stats)
            
            # 3. GPU Stats (Try nvidia-smi, works on Windows if installed)
            gpu_usage = 0.0
            try:
                # 0x08000000 is CREATE_NO_WINDOW
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, creationflags=0x08000000
                )
                if res.returncode == 0:
                    gpu_usage = float(res.stdout.strip())
            except Exception:
                pass
            self.gpu_update.emit(gpu_usage)
            
            # 4. Disk Stats (Windows)
            disks_data = {}
            try:
                partitions = psutil.disk_partitions()
                for part in partitions:
                    if 'cdrom' in part.opts or part.fstype == '':
                        continue
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disks_data[part.device] = {
                            "model": f"Local Disk ({part.device})", 
                            "size": usage.total, 
                            "used": usage.used, 
                            "percent": usage.percent
                        }
                    except (PermissionError, OSError):
                        continue
                self.disk_update.emit(disks_data)
            except Exception:
                pass

            # 4.5 Disk IO Speed
            try:
                current_disk_io = psutil.disk_io_counters()
                current_time = time.time()
                time_delta = current_time - self.last_time
                
                if current_disk_io and self.last_disk_io and time_delta > 0:
                    read_bytes = current_disk_io.read_bytes - self.last_disk_io.read_bytes
                    write_bytes = current_disk_io.write_bytes - self.last_disk_io.write_bytes
                    self.disk_io_update.emit({
                        "read": read_bytes / time_delta,
                        "write": write_bytes / time_delta
                    })
                self.last_disk_io = current_disk_io
            except Exception:
                pass

            # 4. Network Stats
            try:
                current_net_io = psutil.net_io_counters()
                current_time = time.time() # Update time once per loop roughly
                time_delta = current_time - self.last_time
                
                if time_delta > 0:
                    bytes_sent = current_net_io.bytes_sent - self.last_net_io.bytes_sent
                    bytes_recv = current_net_io.bytes_recv - self.last_net_io.bytes_recv
                    self.network_update.emit({
                        "upload": bytes_sent / time_delta,
                        "download": bytes_recv / time_delta
                    })
                
                self.last_net_io = current_net_io
                self.last_time = current_time
            except Exception:
                pass

            # 5. Temperatures
            try:
                # Attempt to read sensors even on Windows (might be empty)
                temps = {}
                try: temps = psutil.sensors_temperatures()
                except: pass
                
                temp_data = {}
                
                def find_entry(entries, search_labels):
                    for e in entries:
                        if not e.label: continue
                        for sl in search_labels:
                            if sl.lower() in e.label.lower():
                                return e.current
                    return None

                # 1. CPU
                cpu_temp = None
                if 'coretemp' in temps:
                    cpu_temp = find_entry(temps['coretemp'], ['Package id 0', 'Package'])
                    if cpu_temp is None and temps['coretemp']:
                        cpu_temp = max(e.current for e in temps['coretemp'])
                elif 'k10temp' in temps:
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
                
                # NVIDIA fallback (Works on Windows)
                if gpu_temp is None:
                        try:
                            # 0x08000000 is CREATE_NO_WINDOW
                            res = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, creationflags=0x08000000)
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

                # 4. Fill remaining slots
                processed_keys = ['coretemp', 'k10temp', 'amdgpu', 'nouveau', 'nvme', 'drivetemp']
                for name, entries in temps.items():
                    if len(temp_data) >= 5: break
                    if name in processed_keys: continue
                    added = 0
                    for entry in entries:
                        if len(temp_data) >= 5 or added >= 2: break
                        label = f"{name} {entry.label or ''}".strip()
                        temp_data[label] = entry.current
                        added += 1

                if not temp_data:
                    # Windows Fallback if absolutely nothing found
                    temp_data = {"CPU": 0.0, "GPU": 0.0}

                self.temp_update.emit(temp_data)
            except Exception:
                pass

            # 6. Fans
            self.fan_update.emit({})

            # 7. Process List
            try:
                # Update process cache
                current_pids = set()
                for p in psutil.process_iter(['pid']):
                    pid = p.info['pid']
                    current_pids.add(pid)
                    if pid not in self.procs:
                        try:
                            proc = psutil.Process(pid)
                            proc.cpu_percent(interval=None)
                            self.procs[pid] = proc
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                
                dead_pids = set(self.procs.keys()) - current_pids
                for pid in dead_pids:
                    del self.procs[pid]

                processes = []
                total_pss = 0 # On Windows we'll use RSS as PSS approximation for the sum logic
                
                for pid, p in self.procs.items():
                    try:
                        try: cpu = p.cpu_percent(interval=None) / self.cpu_count
                        except: cpu = 0.0
                        
                        with p.oneshot():
                            try: name = p.name()
                            except: name = "Unknown"

                            try:
                                mem_info = p.memory_info() # Windows: rss, vms, num_page_faults, peak_wset, wset, peak_paged_pool, paged_pool, peak_nonpaged_pool, nonpaged_pool, pagefile, peak_pagefile, private
                            except:
                                class DummyMem:
                                    rss = 0
                                    vms = 0
                                    private = 0
                                mem_info = DummyMem()
                            
                            # On Windows, 'private' or 'rss' is the best we have.
                            # We use RSS for consistency with Linux logic
                            val = mem_info.rss
                            total_pss += val
                            mem_percent = (val / self.mem_total) * 100
                            
                            try:
                                # Windows doesn't provide swap per process easily via psutil standard calls
                                mem_swap = 0 
                            except:
                                mem_swap = 0

                            try: ppid = p.ppid()
                            except: ppid = 0
                            
                            try: io = p.io_counters()
                            except: io = None
                            
                            try: num_threads = p.num_threads()
                            except: num_threads = 0
                            
                            try: username = p.username()
                            except: username = ""
                            
                            try: status = p.status()
                            except: status = ""

                            info = {
                                'pid': pid,
                                'name': name,
                                'cpu_percent': cpu,
                                'memory_percent': mem_percent,
                                'ppid': ppid,
                                'io_counters': io,
                                'memory_info': mem_info,
                                'mem_shared': 0, # Shared is hard to get on Windows
                                'mem_swap': mem_swap,
                                'num_threads': num_threads,
                                'username': username,
                                'status': status
                            }
                            processes.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    except Exception:
                        continue
                
                # Normalization
                mem = psutil.virtual_memory()
                total_used = mem.total - mem.available
                
                if total_pss > total_used and total_used > 0:
                    ratio = total_used / total_pss
                    for p in processes:
                        p['memory_percent'] *= ratio
                        
                        # Scale memory_info
                        old_mem = p['memory_info']
                        
                        class ScaledMemInfo:
                            def __init__(self, original, ratio):
                                self.rss = int(original.rss * ratio)
                                self.vms = original.vms
                                self.pss = int(original.rss * ratio)
                                self.shared = 0
                                self.swap = 0
                        
                        p['memory_info'] = ScaledMemInfo(old_mem, ratio)
                        p['mem_shared'] = 0
                    
                    remainder = 0
                else:
                    remainder = max(0, total_used - total_pss)
                
                if remainder > 0:
                     class SysMem:
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
            except Exception as e:
                print(f"Error: {e}")

    def stop(self):
        self.running = False