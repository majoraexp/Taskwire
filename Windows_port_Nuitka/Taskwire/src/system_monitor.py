import platform
import subprocess
import time
import os

import psutil
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# Windows WMI Support
try:
    import wmi
    import pythoncom
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

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
        
        self.wmi_obj = None
        self.ohm_wmi = None
        self.lhm_wmi = None

    def _init_wmi(self):
        """Initialize WMI connections in the worker thread."""
        if not HAS_WMI: return
        try:
            pythoncom.CoInitialize() # Required for WMI in threads
            self.wmi_obj = wmi.WMI()
            
            # Try connecting to OpenHardwareMonitor / LibreHardwareMonitor namespaces
            try:
                self.ohm_wmi = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            except: 
                self.ohm_wmi = None
                
            try:
                self.lhm_wmi = wmi.WMI(namespace="root\\LibreHardwareMonitor")
            except:
                self.lhm_wmi = None
                
        except Exception as e:
            print(f"WMI Init Error: {e}")

    def start_monitoring(self):
        if getattr(self, '_loop_running', False):
            return
        self._loop_running = True
        
        # Initialize WMI in this thread
        self._init_wmi()
        
        # Windows-specific: Check for NVIDIA SMI in path or standard location
        nvidia_smi_path = "nvidia-smi"
        # Common Windows path check could be added, but relying on PATH is standard
        
        # Init CPU counters to avoid first-call spikes
        psutil.cpu_percent(interval=None)
        psutil.cpu_times_percent(interval=None, percpu=True)
        
        while self.running:
            # Sleep at start to ensure valid interval for first iteration
            time.sleep(0.25)

            # 1. CPU Stats
            # psutil works well on Windows for this
            
            # Get Per-Core Usage (for UI Bars)
            times_per_core = psutil.cpu_times_percent(interval=None, percpu=True)
            
            cpu_per_core = []
            
            # Aggregators for Overall calculation (Consistency with Per-Core)
            grand_total = 0.0
            grand_idle = 0.0

            for t in times_per_core:
                # Windows usually returns: user, system, idle, interrupt, dpc
                # Sum them all to normalize, just in case they don't sum to 100
                total = 0.0
                idle = 0.0
                
                # Sum available fields safely
                for field in ['user', 'system', 'idle', 'interrupt', 'dpc']:
                    if hasattr(t, field):
                        val = getattr(t, field)
                        total += val
                        if field == 'idle':
                            idle = val
                
                # Update Grand Totals
                grand_total += total
                grand_idle += idle

                if total > 0:
                    # Calculate busy percentage relative to the reported total
                    busy_pct = ((total - idle) / total) * 100.0
                    cpu_per_core.append(max(0.0, busy_pct))
                else:
                    cpu_per_core.append(0.0)
            
            # Calculate Overall from the aggregated sums
            if grand_total > 0:
                cpu_overall = ((grand_total - grand_idle) / grand_total) * 100.0
            else:
                cpu_overall = 0.0
            
            # CPU Frequency
            cpu_freqs = []
            try:
                freqs = psutil.cpu_freq(percpu=True)
                if freqs:
                    cpu_freqs = [f.current for f in freqs]
                    
                # Fix: If Windows returns only 1 frequency for multiple cores (common limitation),
                # broadcast it to all cores so the UI doesn't look broken.
                if len(cpu_freqs) == 1 and self.cpu_count > 1:
                    cpu_freqs = cpu_freqs * self.cpu_count
            except Exception:
                pass
            
            self.cpu_update.emit(cpu_overall, cpu_per_core, cpu_freqs)
            
            # 2. Memory Stats (RAM + Pagefile/Swap)
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

            # 3. GPU Stats (Windows NVIDIA)
            gpu_usage = 0.0
            try:
                # Try calling nvidia-smi.exe
                # On Windows, shell=False is usually safer/cleaner with subprocess.run if executable is in path
                # Creation flag to hide window might be needed for frozen apps, but here we are a thread
                startupinfo = None
                if platform.system() == "Windows":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                res = subprocess.run(
                    [nvidia_smi_path, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, check=False, startupinfo=startupinfo
                )
                if res.returncode == 0:
                    gpu_usage = float(res.stdout.strip())
            except Exception:
                pass
            self.gpu_update.emit(gpu_usage)
            
            # 4. Disk Stats (Usage)
            # Windows Logic: Use psutil.disk_partitions()
            disks_data = {}
            try:
                partitions = psutil.disk_partitions()
                for part in partitions:
                    # Filter out CD-ROMs or unready drives if necessary
                    if 'cdrom' in part.opts or part.fstype == '':
                        continue
                        
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        # On Windows, device is "C:\", mountpoint is "C:\"
                        # We use device as the key
                        
                        # Windows doesn't usually give "Model" names via psutil
                        # We can try wmic if we want, but "Local Disk" is acceptable for a port
                        model = f"Local Disk ({part.device})"
                        
                        disks_data[part.device] = {
                            "model": model, 
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
                    
                    read_speed = read_bytes / time_delta
                    write_speed = write_bytes / time_delta
                    
                    self.disk_io_update.emit({
                        "read": read_speed,
                        "write": write_speed
                    })
                
                self.last_disk_io = current_disk_io
                
            except Exception:
                pass

            # 4. Network Stats (Speed)
            try:
                current_net_io = psutil.net_io_counters()
                current_time = time.time() # We update this at the end of the loop usually, but here is fine
                # Recalc delta to be safe or reuse?
                # For consistency with original code pattern:
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
            except Exception:
                pass

            # 5. Temperatures
            temp_data = {}
            
            # Method A: PSUtil (Native, usually empty on Windows)
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            label = entries[0].label or name
                            temp_data[label] = entries[0].current
            except Exception:
                pass
            
            # Method B: WMI (OpenHardwareMonitor / LibreHardwareMonitor)
            if HAS_WMI and (self.ohm_wmi or self.lhm_wmi):
                try:
                    w_source = self.lhm_wmi or self.ohm_wmi
                    sensors = w_source.Sensor()
                    for s in sensors:
                        if s.SensorType == u'Temperature':
                            # Cleanup Name
                            name = s.Name
                            if "CPU" in s.Parent: name = f"CPU {name}"
                            elif "GPU" in s.Parent: name = f"GPU {name}"
                            temp_data[name] = s.Value
                except:
                    pass
            
            # Method C: Standard WMI (MSAcpi_ThermalZoneTemperature)
            # Often restricted or raw Kelvin values
            if not temp_data and HAS_WMI:
                # 1. MSAcpi_ThermalZoneTemperature (root/wmi)
                if self.wmi_obj:
                    try:
                        wmi_root = wmi.WMI(namespace="root\\wmi")
                        zones = wmi_root.MSAcpi_ThermalZoneTemperature()
                        for i, z in enumerate(zones):
                            # Convert 0.1K to Celsius: (K - 273.2)
                            temp_c = (z.CurrentTemperature - 2732) / 10.0
                            if temp_c > 0 and temp_c < 120:
                                temp_data[f"ACPI Thermal Zone {i+1}"] = temp_c
                    except:
                        pass

                # 2. Win32_PerfFormattedData_Counters_ThermalZoneInformation (root/cimv2)
                # Sometimes available on newer Windows
                if not temp_data:
                    try:
                        wmi_cimv2 = wmi.WMI(namespace="root\\cimv2")
                        zones = wmi_cimv2.Win32_PerfFormattedData_Counters_ThermalZoneInformation()
                        for i, z in enumerate(zones):
                            # Usually in Celsius or Kelvin? Standard counters often Celsius.
                            # Usually "Temperature" property.
                            if hasattr(z, 'Temperature'):
                                temp_c = float(z.Temperature)
                                # Sanity check (sometimes it returns Kelvin 273+ or 3000+)
                                if temp_c > 200: # Likely Kelvin
                                    temp_c = temp_c - 273.15
                                
                                if temp_c > 0 and temp_c < 120:
                                     temp_data[f"Thermal Zone {i+1}"] = temp_c
                    except:
                        pass

            if not temp_data:
                # Fallback if absolutely nothing found
                pass
                
            self.temp_update.emit(temp_data)

            # 6. Fan Speeds
            fan_data = {}
            
            # Method A: PSUtil
            try:
                fans = psutil.sensors_fans()
                if fans:
                    for name, entries in fans.items():
                        for entry in entries:
                            label = entry.label or name
                            fan_data[label] = entry.current
            except Exception:
                pass
                
            # Method B: WMI (OHM/LHM)
            if not fan_data and HAS_WMI and (self.ohm_wmi or self.lhm_wmi):
                try:
                    w_source = self.lhm_wmi or self.ohm_wmi
                    sensors = w_source.Sensor()
                    for s in sensors:
                        if s.SensorType == u'Fan':
                            fan_data[s.Name] = s.Value
                except:
                    pass
            
            self.fan_update.emit(fan_data)

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
                total_pss = 0
                
                for pid, p in self.procs.items():
                    try:
                        try:
                            # CPU percent
                            cpu = p.cpu_percent(interval=None) / self.cpu_count
                        except:
                            cpu = 0.0
                        
                        with p.oneshot():
                            try: name = p.name()
                            except: name = "Unknown"

                            # Windows: Treat System Idle Process as 0% CPU
                            if pid == 0 or name == "System Idle Process":
                                cpu = 0.0

                            # Memory
                            try:
                                mem_info = p.memory_info()
                                # Windows: rss is working set, vms is commit charge
                                # private is private working set usually
                            except (psutil.AccessDenied, ValueError):
                                class DummyMem:
                                    rss = 0
                                    vms = 0
                                    private = 0
                                mem_info = DummyMem()
                            
                            val = mem_info.rss
                            total_pss += val # We sum RSS here as approximation for total usage scaling
                            mem_percent = (val / self.mem_total) * 100

                            # Swap on Windows?
                            # psutil.memory_info().pagefile might be relevant but usually isn't swap per se.
                            # We'll set to 0 to avoid complexity or errors reading protected mem.
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
                                'mem_shared': 0, # Windows shared mem is complex to get via psutil efficiently
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
                        # Scale display attributes locally if needed
                        # The UI uses mem_info.rss / 1024 / 1024 usually
                        # We can modify the object or leave it raw. 
                        # The Linux version wrapped it. Let's do the same for consistency.
                        
                        old_mem = p['memory_info']
                        class ScaledMemInfo:
                            def __init__(self, original, ratio):
                                self.rss = int(original.rss * ratio)
                                self.vms = original.vms
                                # Windows specific attributes
                                self.private = getattr(original, 'private', 0)
                        
                        p['memory_info'] = ScaledMemInfo(old_mem, ratio)
                    
                    remainder = 0
                else:
                    remainder = max(0, total_used - total_pss)
                
                if remainder > 0:
                     class SysMem:
                         rss = remainder
                         vms = remainder
                     
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
                        'username': "SYSTEM",
                        'status': "running"
                     }
                     processes.append(sys_entry)

                processes.sort(key=lambda p: p['cpu_percent'] or 0, reverse=True)
                self.process_update.emit(processes)
                self.memory_update.emit(mem_stats)
            except Exception as e:
                print(f"Error fetching processes: {e}")

    def stop(self):
        self.running = False
