#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统信息收集脚本
支持 Linux Ubuntu (ARM 和 x86-64 架构)
输出 data.json 格式的系统信息
"""

import json
import os
import platform
import subprocess
import re
from datetime import datetime, timedelta, timezone
import socket
import urllib.request
import urllib.error
import sys


order_no = os.popen('cat order_no.txt').read().split('\n')[0];
tunnel_id = os.popen('cat tunnel_id.txt').read().split('\n')[0];
cf_domain = os.popen('cat cf_domain.txt').read().split('\n')[0];
spec_id = os.popen('cat spec_id.txt').read().split('\n')[0];
ghost_work_id = os.popen('cat ghost_work_id.txt').read().split('\n')[0];
namespace = os.popen('cat namespace.txt').read().split('\n')[0];



def get_uptime():
    """获取系统运行时间"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_td = timedelta(seconds=uptime_seconds)
            
            days = uptime_td.days
            hours, remainder = divmod(uptime_td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            return {
                "days": days,
                "hours": hours,
                "minutes": minutes,
                "formatted": f"{days} days, {hours} hours, {minutes} minutes"
            }
    except Exception as e:
        return {
            "days": 0,
            "hours": 0,
            "minutes": 0,
            "formatted": "Unknown"
        }

def get_cpu_info():
    """获取 CPU 信息"""
    cpu_info = {
        "model": "Unknown",
        "cores": 0,
        "threads": 0,
        "frequency": "Unknown",
        "maxFrequency": "Unknown",
        "minFrequency": "Unknown",
        "architecture": platform.machine(),
        "cache": {
            "l1": "Unknown",
            "l2": "Unknown",
            "l3": "Unknown"
        },
        "usage": 0.0,
        "loadAverage": {
            "1min": 0.0,
            "5min": 0.0,
            "15min": 0.0
        }
    }
    
    try:
        # 获取 CPU 型号和核心数
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            
            # 检测架构
            arch = platform.machine()
            
            if 'arm' in arch.lower() or 'aarch64' in arch.lower():
                # ARM 架构
                model_match = re.search(r'Model\s*:\s*(.+)', cpuinfo)
                if model_match:
                    cpu_info['model'] = model_match.group(1).strip()
                else:
                    hardware_match = re.search(r'Hardware\s*:\s*(.+)', cpuinfo)
                    if hardware_match:
                        cpu_info['model'] = hardware_match.group(1).strip()
            else:
                # x86-64 架构
                model_match = re.search(r'model name\s*:\s*(.+)', cpuinfo)
                if model_match:
                    cpu_info['model'] = model_match.group(1).strip()
            
            # 计算核心数
            processors = cpuinfo.count('processor')
            cpu_info['cores'] = processors
            cpu_info['threads'] = processors
        
        # 获取 CPU 当前频率
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()
                freq_match = re.search(r'cpu MHz\s*:\s*(.+)', content)
                if freq_match:
                    freq = float(freq_match.group(1).strip())
                    cpu_info['frequency'] = f"{freq/1000:.2f} GHz"
                else:
                    # ARM 架构可能没有这个字段
                    freq_match = re.search(r'BogoMIPS\s*:\s*(.+)', content)
                    if freq_match:
                        freq = float(freq_match.group(1).strip())
                        cpu_info['frequency'] = f"{freq/1000:.2f} GHz (BogoMIPS)"
        except:
            pass
        
        # 获取 CPU 最大和最小频率（从 cpufreq）
        try:
            # 尝试读取 CPU 0 的频率信息
            base_path = '/sys/devices/system/cpu/cpu0/cpufreq'
            
            # 最大频率
            try:
                with open(f'{base_path}/cpuinfo_max_freq', 'r') as f:
                    max_freq = int(f.read().strip()) / 1000  # kHz to MHz
                    cpu_info['maxFrequency'] = f"{max_freq/1000:.2f} GHz"
            except:
                pass
            
            # 最小频率
            try:
                with open(f'{base_path}/cpuinfo_min_freq', 'r') as f:
                    min_freq = int(f.read().strip()) / 1000  # kHz to MHz
                    cpu_info['minFrequency'] = f"{min_freq/1000:.2f} GHz"
            except:
                pass
                
        except:
            pass
        
        # 获取 CPU 使用率
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                values = line.split()[1:8]
                user, nice, system, idle, iowait, irq, softirq = map(int, values)
                total = user + nice + system + idle + iowait + irq + softirq
                usage = ((total - idle) / total) * 100
                cpu_info['usage'] = round(usage, 1)
        except:
            pass
        
        # 获取负载平均值
        try:
            with open('/proc/loadavg', 'r') as f:
                loadavg = f.read().split()
                cpu_info['loadAverage'] = {
                    "1min": float(loadavg[0]),
                    "5min": float(loadavg[1]),
                    "15min": float(loadavg[2])
                }
        except:
            pass
            
    except Exception as e:
        pass
    
    return cpu_info

def get_memory_info():
    """获取内存信息"""
    memory_info = {
        "total": 0,
        "used": 0,
        "free": 0,
        "cached": 0,
        "usage": 0.0,
        "unit": "MB",
        "frequency": "Unknown",
        "type": "Unknown"
    }
    
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value)
            
            total = meminfo.get('MemTotal', 0) // 1024  # Convert to MB
            free = meminfo.get('MemFree', 0) // 1024
            available = meminfo.get('MemAvailable', 0) // 1024
            cached = meminfo.get('Cached', 0) // 1024
            buffers = meminfo.get('Buffers', 0) // 1024
            
            used = total - available
            usage = (used / total * 100) if total > 0 else 0
            
            memory_info = {
                "total": total,
                "used": used,
                "free": free,
                "cached": cached,
                "usage": round(usage, 1),
                "unit": "MB",
                "frequency": "Unknown",
                "type": "Unknown"
            }
    except Exception as e:
        pass
    
    # 尝试获取内存频率和类型（使用 dmidecode 或 lshw）
    try:
        # 方法1: 使用 dmidecode（需要 root 权限）
        result = subprocess.run(['dmidecode', '--type', 'memory'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout
            
            # 查找内存频率
            speed_match = re.search(r'Speed:\s+(\d+)\s+MHz', output)
            if speed_match:
                speed = int(speed_match.group(1))
                memory_info['frequency'] = f"{speed} MHz"
            
            # 查找内存类型
            type_match = re.search(r'Type:\s+(\w+)', output)
            if type_match:
                memory_info['type'] = type_match.group(1)
    except:
        pass
    
    # 方法2: 如果 dmidecode 失败，尝试从 /sys 读取
    if memory_info['frequency'] == "Unknown":
        try:
            # 尝试读取 DDR 频率信息
            for i in range(10):  # 检查前 10 个内存槽位
                path = f'/sys/devices/system/edac/mc/mc0/dimm{i}/dimm_speed'
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        speed = f.read().strip()
                        if speed:
                            memory_info['frequency'] = speed
                            break
        except:
            pass
    
    return memory_info

def get_disk_info():
    """获取磁盘信息"""
    disk_info = {
        "total": 0,
        "used": 0,
        "free": 0,
        "usage": 0.0,
        "unit": "GB",
        "partitions": []
    }
    
    try:
        # 获取根分区信息
        result = subprocess.run(['df', '-BG', '/'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 4:
                total = int(parts[1].replace('G', ''))
                used = int(parts[2].replace('G', ''))
                available = int(parts[3].replace('G', ''))
                usage = (used / total * 100) if total > 0 else 0
                
                disk_info['total'] = total
                disk_info['used'] = used
                disk_info['free'] = available
                disk_info['usage'] = round(usage, 1)
        
        # 获取分区信息
        partitions = ['/', '/home', '/var']
        for partition in partitions:
            try:
                result = subprocess.run(['df', '-BG', partition], capture_output=True, text=True)
                lines = result.stdout.split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 6:
                        total = int(parts[1].replace('G', ''))
                        used = int(parts[2].replace('G', ''))
                        available = int(parts[3].replace('G', ''))
                        usage = (used / total * 100) if total > 0 else 0
                        
                        # 获取文件系统类型
                        fs_type = parts[0]
                        
                        disk_info['partitions'].append({
                            "mount": partition,
                            "filesystem": fs_type,
                            "total": total,
                            "used": used,
                            "available": available,
                            "usage": round(usage, 1)
                        })
            except:
                pass
                
    except Exception as e:
        pass
    
    return disk_info

def get_network_info():
    """获取网络信息"""
    network_info = {
        "interfaces": [],
        "totalTraffic": {
            "upload": 0,
            "download": 0,
            "uploadFormatted": "0 B",
            "downloadFormatted": "0 B"
        },
        "connections": 0,
        "publicIP": "Unknown"
    }
    
    try:
        # 获取网络接口信息
        result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
        interfaces_data = result.stdout
        
        # 解析网络接口
        interface_pattern = re.compile(r'^\d+:\s+(\S+):.*?state\s+(\S+).*?inet\s+(\S+)', 
                                       re.MULTILINE | re.DOTALL)
        
        for match in interface_pattern.finditer(interfaces_data):
            interface_name = match.group(1)
            status = match.group(2)
            ip = match.group(3).split('/')[0]
            
            # 获取 MAC 地址
            mac_match = re.search(r'link/ether\s+(\S+)', interfaces_data[match.start():match.end()])
            mac = mac_match.group(1) if mac_match else "N/A"
            
            # 获取流量信息
            traffic = get_interface_traffic(interface_name)
            
            network_info['interfaces'].append({
                "name": interface_name,
                "status": status,
                "ip": ip,
                "mac": mac,
                "traffic": traffic
            })
        
        # 计算总流量
        total_rx = sum(iface['traffic']['rx'] for iface in network_info['interfaces'])
        total_tx = sum(iface['traffic']['tx'] for iface in network_info['interfaces'])
        
        network_info['totalTraffic'] = {
            "upload": total_tx,
            "download": total_rx,
            "uploadFormatted": format_bytes(total_tx),
            "downloadFormatted": format_bytes(total_rx)
        }
        
        # 获取连接数
        try:
            result = subprocess.run(['ss', '-s'], capture_output=True, text=True)
            match = re.search(r'TCP:\s+(\d+)', result.stdout)
            if match:
                network_info['connections'] = int(match.group(1))
        except:
            pass
        
        # 获取公网 IP
        try:
            result = subprocess.run(['curl', '-s', 'ifconfig.me'], 
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                network_info['publicIP'] = result.stdout.strip()
        except:
            pass
            
    except Exception as e:
        pass
    
    return network_info

def get_interface_traffic(interface_name):
    """获取网络接口流量"""
    traffic = {
        "rx": 0,
        "tx": 0,
        "rxFormatted": "0 B",
        "txFormatted": "0 B"
    }
    
    try:
        with open(f'/proc/net/dev', 'r') as f:
            for line in f:
                if interface_name in line:
                    parts = line.split()
                    # 接收字节数在第2列，发送字节数在第10列
                    rx_bytes = int(parts[1])
                    tx_bytes = int(parts[9])
                    
                    traffic = {
                        "rx": rx_bytes,
                        "tx": tx_bytes,
                        "rxFormatted": format_bytes(rx_bytes),
                        "txFormatted": format_bytes(tx_bytes)
                    }
                    break
    except:
        pass
    
    return traffic

def format_bytes(bytes_value):
    """格式化字节数"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def get_system_info():
    """获取系统信息"""
    system_info = {
        "os": "Unknown",
        "kernel": "Unknown",
        "uptime": get_uptime(),
        "processCount": 0,
        "timezone": "Unknown",
        "bootTime": "Unknown"
    }
    
    try:
        # 获取 OS 信息
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release', 'r') as f:
                content = f.read()
                pretty_name = re.search(r'PRETTY_NAME="(.+)"', content)
                if pretty_name:
                    system_info['os'] = pretty_name.group(1)
        
        # 获取内核版本
        system_info['kernel'] = platform.release()
        
        # 获取进程数
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        system_info['processCount'] = len(result.stdout.split('\n')) - 1
        
        # 获取时区
        if os.path.exists('/etc/timezone'):
            with open('/etc/timezone', 'r') as f:
                system_info['timezone'] = f.read().strip()
        else:
            result = subprocess.run(['timedatectl', 'show'], capture_output=True, text=True)
            tz_match = re.search(r'Timezone=(.+)', result.stdout)
            if tz_match:
                system_info['timezone'] = tz_match.group(1)
        
        # 获取启动时间
        result = subprocess.run(['uptime', '-s'], capture_output=True, text=True)
        if result.returncode == 0:
            boot_time = result.stdout.strip()
            # 转换为 ISO 格式
            dt = datetime.strptime(boot_time, '%Y-%m-%d %H:%M:%S')
            system_info['bootTime'] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            
    except Exception as e:
        pass
    
    return system_info

def get_hostname():
    """获取主机名"""
    try:
        return socket.gethostname()
    except:
        return "unknown-host"

def get_server_location():
    """获取服务器位置信息（通过 Cloudflare Trace API）"""
    
    # Cloudflare 数据中心代码到机场代码和城市信息的映射
    cf_colo_mapping = {
        "FRA": {"airportCode": "FRA", "airportName": "法兰克福", "country": "DE", "countryName": "德国", "city": "Frankfurt", "datacenter": "CF-FRA"},
        "LHR": {"airportCode": "LHR", "airportName": "伦敦", "country": "GB", "countryName": "英国", "city": "London", "datacenter": "CF-LHR"},
        "CDG": {"airportCode": "CDG", "airportName": "巴黎", "country": "FR", "countryName": "法国", "city": "Paris", "datacenter": "CF-CDG"},
        "AMS": {"airportCode": "AMS", "airportName": "阿姆斯特丹", "country": "NL", "countryName": "荷兰", "city": "Amsterdam", "datacenter": "CF-AMS"},
        "LAX": {"airportCode": "LAX", "airportName": "洛杉矶", "country": "US", "countryName": "美国", "city": "Los Angeles", "datacenter": "CF-LAX"},
        "SJC": {"airportCode": "SJC", "airportName": "圣何塞", "country": "US", "countryName": "美国", "city": "San Jose", "datacenter": "CF-SJC"},
        "SFO": {"airportCode": "SFO", "airportName": "旧金山", "country": "US", "countryName": "美国", "city": "San Francisco", "datacenter": "CF-SFO"},
        "SEA": {"airportCode": "SEA", "airportName": "西雅图", "country": "US", "countryName": "美国", "city": "Seattle", "datacenter": "CF-SEA"},
        "ORD": {"airportCode": "ORD", "airportName": "芝加哥", "country": "US", "countryName": "美国", "city": "Chicago", "datacenter": "CF-ORD"},
        "DFW": {"airportCode": "DFW", "airportName": "达拉斯", "country": "US", "countryName": "美国", "city": "Dallas", "datacenter": "CF-DFW"},
        "ATL": {"airportCode": "ATL", "airportName": "亚特兰大", "country": "US", "countryName": "美国", "city": "Atlanta", "datacenter": "CF-ATL"},
        "MIA": {"airportCode": "MIA", "airportName": "迈阿密", "country": "US", "countryName": "美国", "city": "Miami", "datacenter": "CF-MIA"},
        "BOS": {"airportCode": "BOS", "airportName": "波士顿", "country": "US", "countryName": "美国", "city": "Boston", "datacenter": "CF-BOS"},
        "EWR": {"airportCode": "EWR", "airportName": "纽约纽瓦克", "country": "US", "countryName": "美国", "city": "Newark", "datacenter": "CF-EWR"},
        "IAD": {"airportCode": "IAD", "airportName": "华盛顿杜勒斯", "country": "US", "countryName": "美国", "city": "Washington", "datacenter": "CF-IAD"},
        "PHX": {"airportCode": "PHX", "airportName": "凤凰城", "country": "US", "countryName": "美国", "city": "Phoenix", "datacenter": "CF-PHX"},
        "DEN": {"airportCode": "DEN", "airportName": "丹佛", "country": "US", "countryName": "美国", "city": "Denver", "datacenter": "CF-DEN"},
        "LAS": {"airportCode": "LAS", "airportName": "拉斯维加斯", "country": "US", "countryName": "美国", "city": "Las Vegas", "datacenter": "CF-LAS"},
        "NRT": {"airportCode": "NRT", "airportName": "东京成田", "country": "JP", "countryName": "日本", "city": "Tokyo", "datacenter": "CF-NRT"},
        "HND": {"airportCode": "HND", "airportName": "东京羽田", "country": "JP", "countryName": "日本", "city": "Tokyo", "datacenter": "CF-HND"},
        "KIX": {"airportCode": "KIX", "airportName": "大阪", "country": "JP", "countryName": "日本", "city": "Osaka", "datacenter": "CF-KIX"},
        "ICN": {"airportCode": "ICN", "airportName": "首尔", "country": "KR", "countryName": "韩国", "city": "Seoul", "datacenter": "CF-ICN"},
        "HKG": {"airportCode": "HKG", "airportName": "香港", "country": "HK", "countryName": "中国香港", "city": "Hong Kong", "datacenter": "CF-HKG"},
        "SIN": {"airportCode": "SIN", "airportName": "新加坡", "country": "SG", "countryName": "新加坡", "city": "Singapore", "datacenter": "CF-SIN"},
        "SYD": {"airportCode": "SYD", "airportName": "悉尼", "country": "AU", "countryName": "澳大利亚", "city": "Sydney", "datacenter": "CF-SYD"},
        "MEL": {"airportCode": "MEL", "airportName": "墨尔本", "country": "AU", "countryName": "澳大利亚", "city": "Melbourne", "datacenter": "CF-MEL"},
        "DXB": {"airportCode": "DXB", "airportName": "迪拜", "country": "AE", "countryName": "阿联酋", "city": "Dubai", "datacenter": "CF-DXB"},
        "PEK": {"airportCode": "PEK", "airportName": "北京", "country": "CN", "countryName": "中国", "city": "Beijing", "datacenter": "CF-PEK"},
        "PVG": {"airportCode": "PVG", "airportName": "上海", "country": "CN", "countryName": "中国", "city": "Shanghai", "datacenter": "CF-PVG"},
        "CAN": {"airportCode": "CAN", "airportName": "广州", "country": "CN", "countryName": "中国", "city": "Guangzhou", "datacenter": "CF-CAN"},
        "SZX": {"airportCode": "SZX", "airportName": "深圳", "country": "CN", "countryName": "中国", "city": "Shenzhen", "datacenter": "CF-SZX"},
        "TPE": {"airportCode": "TPE", "airportName": "台北", "country": "TW", "countryName": "中国台湾", "city": "Taipei", "datacenter": "CF-TPE"},
        "BLR": {"airportCode": "BLR", "airportName": "班加罗尔", "country": "IN", "countryName": "印度", "city": "Bangalore", "datacenter": "CF-BLR"},
        "BOM": {"airportCode": "BOM", "airportName": "孟买", "country": "IN", "countryName": "印度", "city": "Mumbai", "datacenter": "CF-BOM"},
        "GRU": {"airportCode": "GRU", "airportName": "圣保罗", "country": "BR", "countryName": "巴西", "city": "Sao Paulo", "datacenter": "CF-GRU"},
        "SCL": {"airportCode": "SCL", "airportName": "圣地亚哥", "country": "CL", "countryName": "智利", "city": "Santiago", "datacenter": "CF-SCL"},
        "JNB": {"airportCode": "JNB", "airportName": "约翰内斯堡", "country": "ZA", "countryName": "南非", "city": "Johannesburg", "datacenter": "CF-JNB"},
        "CAI": {"airportCode": "CAI", "airportName": "开罗", "country": "EG", "countryName": "埃及", "city": "Cairo", "datacenter": "CF-CAI"},
        "TLV": {"airportCode": "TLV", "airportName": "特拉维夫", "country": "IL", "countryName": "以色列", "city": "Tel Aviv", "datacenter": "CF-TLV"},
        "IST": {"airportCode": "IST", "airportName": "伊斯坦布尔", "country": "TR", "countryName": "土耳其", "city": "Istanbul", "datacenter": "CF-IST"},
        "MOW": {"airportCode": "MOW", "airportName": "莫斯科", "country": "RU", "countryName": "俄罗斯", "city": "Moscow", "datacenter": "CF-MOW"},
        "HEL": {"airportCode": "HEL", "airportName": "赫尔辛基", "country": "FI", "countryName": "芬兰", "city": "Helsinki", "datacenter": "CF-HEL"},
        "ARN": {"airportCode": "ARN", "airportName": "斯德哥尔摩", "country": "SE", "countryName": "瑞典", "city": "Stockholm", "datacenter": "CF-ARN"},
        "OSL": {"airportCode": "OSL", "airportName": "奥斯陆", "country": "NO", "countryName": "挪威", "city": "Oslo", "datacenter": "CF-OSL"},
        "CPH": {"airportCode": "CPH", "airportName": "哥本哈根", "country": "DK", "countryName": "丹麦", "city": "Copenhagen", "datacenter": "CF-CPH"},
        "WAW": {"airportCode": "WAW", "airportName": "华沙", "country": "PL", "countryName": "波兰", "city": "Warsaw", "datacenter": "CF-WAW"},
        "VIE": {"airportCode": "VIE", "airportName": "维也纳", "country": "AT", "countryName": "奥地利", "city": "Vienna", "datacenter": "CF-VIE"},
        "MAD": {"airportCode": "MAD", "airportName": "马德里", "country": "ES", "countryName": "西班牙", "city": "Madrid", "datacenter": "CF-MAD"},
        "BCN": {"airportCode": "BCN", "airportName": "巴塞罗那", "country": "ES", "countryName": "西班牙", "city": "Barcelona", "datacenter": "CF-BCN"},
        "MXP": {"airportCode": "MXP", "airportName": "米兰", "country": "IT", "countryName": "意大利", "city": "Milan", "datacenter": "CF-MXP"},
        "FCO": {"airportCode": "FCO", "airportName": "罗马", "country": "IT", "countryName": "意大利", "city": "Rome", "datacenter": "CF-FCO"},
        "ATH": {"airportCode": "ATH", "airportName": "雅典", "country": "GR", "countryName": "希腊", "city": "Athens", "datacenter": "CF-ATH"},
        "LIS": {"airportCode": "LIS", "airportName": "里斯本", "country": "PT", "countryName": "葡萄牙", "city": "Lisbon", "datacenter": "CF-LIS"},
        "BRU": {"airportCode": "BRU", "airportName": "布鲁塞尔", "country": "BE", "countryName": "比利时", "city": "Brussels", "datacenter": "CF-BRU"},
        "ZRH": {"airportCode": "ZRH", "airportName": "苏黎世", "country": "CH", "countryName": "瑞士", "city": "Zurich", "datacenter": "CF-ZRH"},
        "MUC": {"airportCode": "MUC", "airportName": "慕尼黑", "country": "DE", "countryName": "德国", "city": "Munich", "datacenter": "CF-MUC"},
        "DUS": {"airportCode": "DUS", "airportName": "杜塞尔多夫", "country": "DE", "countryName": "德国", "city": "Dusseldorf", "datacenter": "CF-DUS"},
        "HAM": {"airportCode": "HAM", "airportName": "汉堡", "country": "DE", "countryName": "德国", "city": "Hamburg", "datacenter": "CF-HAM"},
        "BER": {"airportCode": "BER", "airportName": "柏林", "country": "DE", "countryName": "德国", "city": "Berlin", "datacenter": "CF-BER"},
        "YYZ": {"airportCode": "YYZ", "airportName": "多伦多", "country": "CA", "countryName": "加拿大", "city": "Toronto", "datacenter": "CF-YYZ"},
        "YVR": {"airportCode": "YVR", "airportName": "温哥华", "country": "CA", "countryName": "加拿大", "city": "Vancouver", "datacenter": "CF-YVR"},
        "YUL": {"airportCode": "YUL", "airportName": "蒙特利尔", "country": "CA", "countryName": "加拿大", "city": "Montreal", "datacenter": "CF-YUL"},
        "MEX": {"airportCode": "MEX", "airportName": "墨西哥城", "country": "MX", "countryName": "墨西哥", "city": "Mexico City", "datacenter": "CF-MEX"},
        "BOG": {"airportCode": "BOG", "airportName": "波哥大", "country": "CO", "countryName": "哥伦比亚", "city": "Bogota", "datacenter": "CF-BOG"},
        "LIM": {"airportCode": "LIM", "airportName": "利马", "country": "PE", "countryName": "秘鲁", "city": "Lima", "datacenter": "CF-LIM"},
        "BAH": {"airportCode": "BAH", "airportName": "巴林", "country": "BH", "countryName": "巴林", "city": "Bahrain", "datacenter": "CF-BAH"},
        "RUH": {"airportCode": "RUH", "airportName": "利雅得", "country": "SA", "countryName": "沙特阿拉伯", "city": "Riyadh", "datacenter": "CF-RUH"},
        "JED": {"airportCode": "JED", "airportName": "吉达", "country": "SA", "countryName": "沙特阿拉伯", "city": "Jeddah", "datacenter": "CF-JED"},
        "KWI": {"airportCode": "KWI", "airportName": "科威特", "country": "KW", "countryName": "科威特", "city": "Kuwait", "datacenter": "CF-KWI"},
        "DOH": {"airportCode": "DOH", "airportName": "多哈", "country": "QA", "countryName": "卡塔尔", "city": "Doha", "datacenter": "CF-DOH"},
        "AMM": {"airportCode": "AMM", "airportName": "安曼", "country": "JO", "countryName": "约旦", "city": "Amman", "datacenter": "CF-AMM"},
        "KHI": {"airportCode": "KHI", "airportName": "卡拉奇", "country": "PK", "countryName": "巴基斯坦", "city": "Karachi", "datacenter": "CF-KHI"},
        "DEL": {"airportCode": "DEL", "airportName": "德里", "country": "IN", "countryName": "印度", "city": "Delhi", "datacenter": "CF-DEL"},
        "MAA": {"airportCode": "MAA", "airportName": "金奈", "country": "IN", "countryName": "印度", "city": "Chennai", "datacenter": "CF-MAA"},
        "CCU": {"airportCode": "CCU", "airportName": "加尔各答", "country": "IN", "countryName": "印度", "city": "Kolkata", "datacenter": "CF-CCU"},
        "BKK": {"airportCode": "BKK", "airportName": "曼谷", "country": "TH", "countryName": "泰国", "city": "Bangkok", "datacenter": "CF-BKK"},
        "SGN": {"airportCode": "SGN", "airportName": "胡志明市", "country": "VN", "countryName": "越南", "city": "Ho Chi Minh", "datacenter": "CF-SGN"},
        "HAN": {"airportCode": "HAN", "airportName": "河内", "country": "VN", "countryName": "越南", "city": "Hanoi", "datacenter": "CF-HAN"},
        "JKT": {"airportCode": "JKT", "airportName": "雅加达", "country": "ID", "countryName": "印度尼西亚", "city": "Jakarta", "datacenter": "CF-JKT"},
        "MNL": {"airportCode": "MNL", "airportName": "马尼拉", "country": "PH", "countryName": "菲律宾", "city": "Manila", "datacenter": "CF-MNL"},
        "KUL": {"airportCode": "KUL", "airportName": "吉隆坡", "country": "MY", "countryName": "马来西亚", "city": "Kuala Lumpur", "datacenter": "CF-KUL"},
        "PEN": {"airportCode": "PEN", "airportName": "槟城", "country": "MY", "countryName": "马来西亚", "city": "Penang", "datacenter": "CF-PEN"},
        "PER": {"airportCode": "PER", "airportName": "珀斯", "country": "AU", "countryName": "澳大利亚", "city": "Perth", "datacenter": "CF-PER"},
        "BNE": {"airportCode": "BNE", "airportName": "布里斯班", "country": "AU", "countryName": "澳大利亚", "city": "Brisbane", "datacenter": "CF-BNE"},
        "ADL": {"airportCode": "ADL", "airportName": "阿德莱德", "country": "AU", "countryName": "澳大利亚", "city": "Adelaide", "datacenter": "CF-ADL"},
        "AKL": {"airportCode": "AKL", "airportName": "奥克兰", "country": "NZ", "countryName": "新西兰", "city": "Auckland", "datacenter": "CF-AKL"},
        "WLG": {"airportCode": "WLG", "airportName": "惠灵顿", "country": "NZ", "countryName": "新西兰", "city": "Wellington", "datacenter": "CF-WLG"},
    }
    
    # 国家代码到国家名称的映射
    country_names = {
        "US": "美国", "CN": "中国", "JP": "日本", "KR": "韩国", "GB": "英国",
        "DE": "德国", "FR": "法国", "NL": "荷兰", "AU": "澳大利亚", "CA": "加拿大",
        "SG": "新加坡", "HK": "中国香港", "TW": "中国台湾", "IN": "印度", "BR": "巴西",
        "RU": "俄罗斯", "AE": "阿联酋", "IT": "意大利", "ES": "西班牙", "CH": "瑞士",
        "SE": "瑞典", "NO": "挪威", "DK": "丹麦", "FI": "芬兰", "PL": "波兰",
        "AT": "奥地利", "BE": "比利时", "PT": "葡萄牙", "GR": "希腊", "TR": "土耳其",
        "IL": "以色列", "EG": "埃及", "ZA": "南非", "CL": "智利", "CO": "哥伦比亚",
        "PE": "秘鲁", "MX": "墨西哥", "AR": "阿根廷", "TH": "泰国", "VN": "越南",
        "ID": "印度尼西亚", "PH": "菲律宾", "MY": "马来西亚", "NZ": "新西兰",
        "SA": "沙特阿拉伯", "BH": "巴林", "KW": "科威特", "QA": "卡塔尔", "JO": "约旦",
        "PK": "巴基斯坦"
    }
    
    try:
        # 访问 Cloudflare Trace API
        url = "https://www.cloudflare.com/cdn-cgi/trace"
        req = urllib.request.Request(url)
        
        # 设置超时和 User-Agent
        req.add_header('User-Agent', 'Mozilla/5.0 (compatible; SystemInfoCollector/1.0)')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            trace_data = response.read().decode('utf-8')
            
        # 解析 trace 数据
        trace_info = {}
        for line in trace_data.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                trace_info[key] = value
        
        # 提取关键信息
        public_ip = trace_info.get('ip', 'Unknown')
        colo = trace_info.get('colo', 'Unknown')  # Cloudflare 数据中心代码
        loc = trace_info.get('loc', 'Unknown')    # 国家代码
        
        # 根据数据中心代码查找位置信息
        if colo in cf_colo_mapping:
            location = cf_colo_mapping[colo].copy()
            location['publicIP'] = public_ip
            return location
        
        # 如果没有找到数据中心映射，使用国家代码
        country_name = country_names.get(loc, loc)
        
        return {
            "airportCode": colo,
            "airportName": f"Cloudflare {colo}",
            "country": loc,
            "countryName": country_name,
            "city": f"City-{colo}",
            "datacenter": f"CF-{colo}",
            "publicIP": public_ip
        }
        
    except urllib.error.URLError as e:
        pass
        # print(f"警告: 无法访问 Cloudflare Trace API: {e}")
    except Exception as e:
        pass
        # print(f"警告: 获取服务器位置信息失败: {e}")
    
    # 如果 API 访问失败，返回默认值
    return {
        "airportCode": "Unknown",
        "airportName": "未知",
        "country": "Unknown",
        "countryName": "未知",
        "city": "Unknown",
        "datacenter": "Unknown"
    }

def get_reference_data():
    """获取参考数据（机场代码和国家代码）"""
    return {
        "airportCodes": {
            "LAX": "洛杉矶",
            "SJC": "圣何塞",
            "SFO": "旧金山",
            "SEA": "西雅图",
            "NYC": "纽约",
            "ORD": "芝加哥",
            "DFW": "达拉斯",
            "ATL": "亚特兰大",
            "MIA": "迈阿密",
            "BOS": "波士顿",
            "JFK": "纽约肯尼迪",
            "EWR": "纽约纽瓦克",
            "LGA": "纽约拉瓜迪亚",
            "PHL": "费城",
            "DCA": "华盛顿里根",
            "IAD": "华盛顿杜勒斯",
            "BWI": "巴尔的摩",
            "CLT": "夏洛特",
            "RDU": "罗利",
            "TPA": "坦帕",
            "MCO": "奥兰多",
            "FLL": "劳德代尔堡",
            "PBI": "棕榈滩",
            "IAH": "休斯顿洲际",
            "HOU": "休斯顿霍比",
            "AUS": "奥斯汀",
            "SAT": "圣安东尼奥",
            "DAL": "达拉斯爱田",
            "DEN": "丹佛",
            "PHX": "凤凰城",
            "LAS": "拉斯维加斯",
            "SAN": "圣地亚哥",
            "BUR": "伯班克",
            "LGB": "长滩",
            "SNA": "圣安娜",
            "OAK": "奥克兰",
            "PDX": "波特兰",
            "SLC": "盐湖城",
            "BOI": "博伊西",
            "RNO": "雷诺",
            "SMF": "萨克拉门托",
            "FAT": "弗雷斯诺",
            "ABQ": "阿尔伯克基",
            "TUS": "图森",
            "ELP": "埃尔帕索",
            "OKC": "俄克拉荷马城",
            "TUL": "塔尔萨",
            "OMA": "奥马哈",
            "MCI": "堪萨斯城",
            "STL": "圣路易斯",
            "MSP": "明尼阿波利斯",
            "DTW": "底特律",
            "CLE": "克利夫兰",
            "CMH": "哥伦布",
            "CVG": "辛辛那提",
            "IND": "印第安纳波利斯",
            "PIT": "匹兹堡",
            "BUF": "水牛城",
            "ROC": "罗切斯特",
            "SYR": "锡拉丘兹",
            "ALB": "奥尔巴尼",
            "HPN": "怀特普莱恩斯",
            "BDL": "哈特福德",
            "PVD": "普罗维登斯",
            "MHT": "曼彻斯特",
            "PWM": "波特兰(缅因)",
            "BTV": "伯灵顿",
            "RICH": "里士满",
            "ORF": "诺福克",
            "GSO": "格林斯伯勒",
            "AVL": "阿什维尔",
            "CHA": "查塔努加",
            "BNA": "纳什维尔",
            "MEM": "孟菲斯",
            "BHM": "伯明翰",
            "HSV": "亨茨维尔",
            "JAX": "杰克逊维尔",
            "RSW": "迈尔斯堡",
            "PNS": "彭萨科拉",
            "MOB": "莫比尔",
            "MSY": "新奥尔良",
            "BTR": "巴吞鲁日",
            "LIT": "小石城",
            "SHV": "什里夫波特",
            "Wichita": "威奇托",
            "DSM": "得梅因",
            "CID": "锡达拉皮兹",
            "MSN": "麦迪逊",
            "GRB": "绿湾",
            "MKE": "密尔沃基",
            "GRR": "大急流城",
            "FNT": "弗林特",
            "LAN": "兰辛",
            "Kalamazoo": "卡拉马祖",
            "SBN": "南本德",
            "FWA": "韦恩堡",
            "EVV": "埃文斯维尔",
            "CAK": "阿克伦",
            "DAY": "代顿",
            "TOL": "托莱多",
            "YNG": "扬斯敦",
            "ERI": "伊利",
            "ABE": "阿伦敦",
            "AVP": "威尔克斯-巴里",
            "HAR": "哈里斯堡",
            "MDT": "米德尔敦",
            "ILG": "威尔明顿",
            "ACY": "大西洋城",
            "TTN": "特伦顿",
            "ISP": "伊斯拉普",
            "SWF": "斯图尔特",
            "LHR": "伦敦",
            "CDG": "巴黎",
            "FRA": "法兰克福",
            "AMS": "阿姆斯特丹",
            "NRT": "东京成田",
            "HND": "东京羽田",
            "KIX": "大阪",
            "ICN": "首尔",
            "HKG": "香港",
            "SIN": "新加坡",
            "SYD": "悉尼",
            "MEL": "墨尔本",
            "DXB": "迪拜",
            "PEK": "北京",
            "PVG": "上海",
            "CAN": "广州",
            "SZX": "深圳"
        },
        "countryCodes": {
            "US": "美国",
            "CN": "中国",
            "JP": "日本",
            "KR": "韩国",
            "GB": "英国",
            "DE": "德国",
            "FR": "法国",
            "NL": "荷兰",
            "AU": "澳大利亚",
            "CA": "加拿大",
            "SG": "新加坡",
            "HK": "中国香港",
            "TW": "中国台湾",
            "IN": "印度",
            "BR": "巴西",
            "RU": "俄罗斯",
            "AE": "阿联酋"
        }
    }

def collect_all_data():
    """收集所有系统数据"""
    data = {
        "server": {
            "status": "online",
            "hostname": get_hostname(),
            "location": get_server_location(),
            "remote_desktop_url": "https://" + tunnel_id + "." + cf_domain,
            "work_id": ghost_work_id,
            "namespace": namespace,
            "order_no": order_no,
            "spec_id": spec_id
        },
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "network": get_network_info(),
        "system": get_system_info(),
        "reference": get_reference_data(),
        "lastUpdate": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    
    return data

def upload_to_server(data, url="https://krabs.shop/api/php/v1/systemInfoUpdate.php"):
    """
    上传 JSON 数据到服务器
    
    参数:
        data: JSON 数据字典
        url: API 接口地址
    
    返回:
        bool: 是否上传成功
    """
    try:
        # 将数据转换为 JSON 字符串
        json_data = json.dumps(data, indent=2, ensure_ascii=False)
        
        # 创建请求
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        req.add_header('User-Agent', 'SystemInfoCollector/1.0')
        
        # 发送 POST 请求

        
        with urllib.request.urlopen(req, data=json_data.encode('utf-8'), timeout=30) as response:
            response_data = response.read().decode('utf-8')
            result = json.loads(response_data)
            
            if result.get('success'):

                return True
            else:

                return False
                
    except urllib.error.URLError as e:
        return False
    except json.JSONDecodeError as e:
        return False
    except Exception as e:
        return False

def main():
    """主函数"""

    # 解析命令行参数
    upload_enabled = True
    filename = None
    
    # 检查命令行参数
    args = sys.argv[1:]
    if '--upload' in args or '-u' in args:
        upload_enabled = True
        # 获取 filename 参数
        for i, arg in enumerate(args):
            if arg in ['--filename', '-f'] and i + 1 < len(args):
                filename = args[i + 1]
                break
        
        # 如果没有指定 filename，使用主机名
        if not filename:
            filename = socket.gethostname()
    
    # 收集数据
    data = collect_all_data()
    
    # 如果启用了上传功能
    if upload_enabled:
        upload_to_server(data)


if __name__ == "__main__":
    main()
