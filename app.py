"""
局域网设备管理Web应用 - 后端
LAN Device Manager - Backend
"""
import os
import sqlite3
import socket
import subprocess
import time
import json
import nmap
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, g, send_from_directory
import os
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# 配置
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'devices.db')
PORT = 5000
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

app = Flask(__name__)
CORS(app)

# 数据库初始化
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # 设备表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address VARCHAR(45) UNIQUE NOT NULL,
            mac_address VARCHAR(17),
            hostname VARCHAR(255),
            device_type VARCHAR(50),
            vendor VARCHAR(100),
            is_online BOOLEAN DEFAULT 0,
            latency FLOAT,
            last_seen DATETIME,
            notes TEXT,
            is_favorite BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 端口表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            port INTEGER NOT NULL,
            protocol VARCHAR(10) DEFAULT 'tcp',
            service VARCHAR(50),
            status VARCHAR(20) DEFAULT 'unknown',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
            UNIQUE(device_id, port, protocol)
        )
    ''')
    
    # 扫描日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            devices_found INTEGER,
            scan_type VARCHAR(20),
            duration FLOAT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 设置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(50) PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # 默认设置
    default_settings = {
        'auto_scan': 'false',
        'scan_interval': '60',
        'scan_ports': '22,80,443,3389,8080,8443,22,21,23,25,53,110,143,3306,5432,6379,27017'
    }
    for key, value in default_settings.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

def get_db():
    """获取数据库连接"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ============ 工具函数 ============

def get_local_network():
    """获取本机局域网信息"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # 推断子网
        parts = local_ip.split('.')
        network = f"{parts[0]}.{parts[1]}.{parts[2]}"
        
        return {
            'local_ip': local_ip,
            'network': network,
            'cidr': f"{network}.0/24"
        }
    except Exception as e:
        return {'local_ip': '192.168.1.1', 'network': '192.168.1', 'cidr': '192.168.1.0/24'}

def get_vendor_from_mac(mac):
    """通过MAC地址获取厂商信息"""
    # 简化的MAC厂商映射
    vendor_prefixes = {
        '00:50:56': 'VMware',
        '00:0C:29': 'VMware',
        '00:1C:42': 'Parallels',
        '08:00:27': 'VirtualBox',
        '52:54:00': 'QEMU',
        'B8:27:EB': 'Raspberry Pi',
        'DC:A6:32': 'Raspberry Pi',
        'E4:5F:01': 'Raspberry Pi',
        '00:1A:2B': 'Intel',
        '00:1E:67': 'Intel',
        '00:22:FA': 'Intel',
        '3C:06:30': 'Apple',
        'A4:5E:60': 'Apple',
        'F0:18:98': 'Apple',
        '00:25:00': 'Apple',
        '00:1F:F3': 'Apple',
        '18:AF:8F': 'Apple',
        '9C:20:7B': 'Apple',
        '00:1F:F3': 'Apple',
        '00:24:36': 'Netgear',
        '44:94:FC': 'Netgear',
        'C0:3F:0E': 'Netgear',
        '00:14:6C': 'Netgear',
        '20:4E:7F': 'Netgear',
        'C8:3A:35': 'Tenda',
        '00:1D:0F': 'TP-Link',
        '50:C7:BF': 'TP-Link',
        '54:C8:0F': 'TP-Link',
        '64:70:02': 'TP-Link',
        '14:CC:20': 'TP-Link',
        '5C:A6:E6': 'Xiaomi',
        '34:80:B3': 'Xiaomi',
        '64:B4:73': 'Xiaomi',
        '34:29:12': 'Xiaomi',
        '64:B4:73': 'Xiaomi',
        '00:9E:C8': 'Xiaomi',
        'F4:F5:D8': 'Xiaomi',
        'F4:F5:E8': 'Xiaomi',
        'B0:E2:35': 'Xiaomi',
        '9C:99:A0': 'NetApp',
        '00:50:56': 'VMware',
        '00:0C:29': 'VMware',
        '00:1C:14': 'VMware',
        '00:1C:42': 'Parallels',
        '08:00:27': 'VirtualBox',
        '52:54:00': 'QEMU/KVM',
        'AC:DE:48': 'Demo',
    }
    
    if mac:
        prefix = mac.upper()[:8]
        return vendor_prefixes.get(prefix, 'Unknown')
    return 'Unknown'

def determine_device_type(hostname, vendor, ports):
    """判断设备类型"""
    hostname_lower = hostname.lower() if hostname else ''
    vendor_lower = vendor.lower() if vendor else ''
    
    # 通过端口判断
    if 22 in ports: return 'Server/Linux'
    if 3389 in ports: return 'Windows PC'
    if 80 in ports or 443 in ports or 8080 in ports: return 'Web Server/Device'
    
    # 通过主机名判断
    keywords = {
        'router': 'Router',
        'gateway': 'Router',
        'switch': 'Switch',
        'printer': 'Printer',
        'print': 'Printer',
        'camera': 'IP Camera',
        'nvr': 'NVR',
        'nas': 'NAS',
        'server': 'Server',
        'desktop': 'Desktop',
        'laptop': 'Laptop',
        'phone': 'Phone',
        'mobile': 'Mobile',
        'tablet': 'Tablet',
        'tv': 'Smart TV',
        'box': 'Set-top Box',
        'pi': 'Raspberry Pi',
        'esp': 'IoT Device',
    }
    
    for keyword, dev_type in keywords.items():
        if keyword in hostname_lower:
            return dev_type
    
    # 通过厂商判断
    vendor_types = {
        'raspberry': 'Single Board Computer',
        'intel': 'Computer',
        'apple': 'Apple Device',
        'netgear': 'Router',
        'tp-link': 'Router',
        'xiaomi': 'Smart Device',
        'cisco': 'Network Device',
        'huawei': 'Network Device',
    }
    
    for v_key, v_type in vendor_types.items():
        if v_key in vendor_lower:
            return v_type
    
    return 'Unknown Device'

def scan_network(cidr):
    """扫描局域网"""
    start_time = time.time()
    devices_found = 0
    
    devices = []
    db = get_db()
    cursor = db.cursor()
    
