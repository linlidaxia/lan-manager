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
    
    # 使用ARP扫描
    try:
        result = subprocess.run(
            ['nmap', '-sn', '-PR', '-oG', '-', cidr],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # 解析nmap结果
        ips = []
        for line in result.stdout.split('\n'):
            if 'Up' in line and '$' in line:
                parts = line.split()
                for part in parts:
                    if part.startswith('$') and not part.startswith('$MAC'):
                        ip = part[1:]
                        if '.' in ip:
                            ips.append(ip)
        
        devices_found = len(ips)
        
    except Exception as e:
        print(f"nmap扫描失败: {e}")
        # 回退到ping扫描
        network_info = get_local_network()
        network = network_info['network']
        for i in range(1, 255):
            ip = f"{network}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex((ip, 80))
                sock.close()
                if result == 0:
                    ips.append(ip)
                    devices_found += 1
            except:
                pass
    
    # 获取每个设备的详细信息
    devices = []
    db = get_db()
    cursor = db.cursor()
    
    for ip in ips:
        try:
            # 获取MAC地址
            mac = None
            hostname = None
            try:
                arp_result = subprocess.run(
                    ['arp', '-n', ip],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in arp_result.stdout.split('\n'):
                    if ip in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            mac = parts[2] if ':' in parts[2] else None
                            break
            except:
                pass
            
            # 尝试获取主机名
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except:
                hostname = None
            
            # 计算延迟
            latency = 0
            try:
                ping_result = subprocess.run(
                    ['ping', '-n', '1', '-w', '1000', ip]  # -n Windows, -c Linux,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                for line in ping_result.stdout.split('\n'):
                    if 'time=' in line:
                        latency = float(line.split('time=')[1].split()[0])
                        break
            except:
                pass
            
            vendor = get_vendor_from_mac(mac)
            
            # 保存到数据库
            cursor.execute('''
                INSERT OR REPLACE INTO devices 
                (ip_address, mac_address, hostname, vendor, is_online, latency, last_seen)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            ''', (ip, mac, hostname, vendor, latency, datetime.now()))
            
            # 获取设备ID
            device_id = cursor.execute('SELECT id FROM devices WHERE ip_address = ?', (ip,)).fetchone()
            if device_id:
                devices.append({
                    'id': device_id[0],
                    'ip_address': ip,
                    'mac_address': mac,
                    'hostname': hostname,
                    'vendor': vendor,
                    'device_type': 'Unknown Device',
                    'is_online': True,
                    'latency': latency,
                    'last_seen': datetime.now().isoformat()
                })
            
        except Exception as e:
            print(f"扫描 {ip} 时出错: {e}")
    
    db.commit()
    
    # 更新离线设备状态
    cursor.execute('UPDATE devices SET is_online = 0, latency = NULL WHERE last_seen < ?', 
                   (datetime.now(),))
    db.commit()
    
    duration = time.time() - start_time
    
    # 记录扫描日志
    cursor.execute('''
        INSERT INTO scan_logs (devices_found, scan_type, duration)
        VALUES (?, ?, ?)
    ''', (devices_found, 'network', duration))
    db.commit()
    
    return devices, devices_found, duration

def scan_ports(device_id, ip, port_list):
    """扫描设备端口"""
    nm = nmap.PortScanner()
    ports_str = ','.join(map(str, port_list))
    
    try:
        nm.scan(ip, ports_str, arguments='-sV -T4')
        
        db = get_db()
        cursor = db.cursor()
        
        for port in port_list:
            try:
                if ip in nm.all_hosts() and port in nm[ip].all_protocols():
                    info = nm[ip][nm[ip].all_protocols()[0]][port]
                    service = info.get('name', 'unknown')
                    status = info.get('state', 'unknown')
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO ports (device_id, port, protocol, service, status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (device_id, port, 'tcp', service, status))
                else:
                    cursor.execute('''
                        INSERT OR REPLACE INTO ports (device_id, port, protocol, service, status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (device_id, port, 'tcp', 'unknown', 'closed'))
            except Exception as e:
                print(f"扫描端口 {port} 失败: {e}")
        
        db.commit()
        return True
    except Exception as e:
        print(f"端口扫描失败: {e}")
        return False

# ============ API路由 ============

# 前端页面路由
@app.route('/')
def index():
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'templates'), 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'templates'), path)

@app.route('/api/network', methods=['GET'])
def get_network_info():
    """获取本机网络信息"""
    return jsonify(get_local_network())

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """获取所有设备"""
    db = get_db()
    cursor = db.cursor()
    
    # 搜索过滤
    search = request.args.get('search', '')
    online_only = request.args.get('online', 'false').lower() == 'true'
    
    query = 'SELECT * FROM devices WHERE 1=1'
    params = []
    
    if search:
        query += ' AND (ip_address LIKE ? OR mac_address LIKE ? OR hostname LIKE ? OR vendor LIKE ?)'
        search_pattern = f'%{search}%'
        params.extend([search_pattern] * 4)
    
    if online_only:
        query += ' AND is_online = 1'
    
    query += ' ORDER BY is_online DESC, last_seen DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    devices = []
    for row in rows:
        devices.append({
            'id': row['id'],
            'ip_address': row['ip_address'],
            'mac_address': row['mac_address'],
            'hostname': row['hostname'],
            'device_type': row['device_type'],
            'vendor': row['vendor'],
            'is_online': bool(row['is_online']),
            'latency': row['latency'],
            'last_seen': row['last_seen'],
            'notes': row['notes'],
            'is_favorite': bool(row['is_favorite']),
            'created_at': row['created_at']
        })
    
    return jsonify(devices)

@app.route('/api/devices/<int:device_id>', methods=['GET'])
def get_device(device_id):
    """获取设备详情"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
    row = cursor.fetchone()
    
    if not row:
        return jsonify({'error': '设备不存在'}), 404
    
    # 获取端口信息
    cursor.execute('SELECT * FROM ports WHERE device_id = ? ORDER BY port', (device_id,))
    port_rows = cursor.fetchall()
    
    ports = []
    for port_row in port_rows:
        ports.append({
            'id': port_row['id'],
            'port': port_row['port'],
            'protocol': port_row['protocol'],
            'service': port_row['service'],
            'status': port_row['status'],
            'notes': port_row['notes']
        })
    
    device = {
        'id': row['id'],
        'ip_address': row['ip_address'],
        'mac_address': row['mac_address'],
        'hostname': row['hostname'],
        'device_type': row['device_type'],
        'vendor': row['vendor'],
        'is_online': bool(row['is_online']),
        'latency': row['latency'],
        'last_seen': row['last_seen'],
        'notes': row['notes'],
        'is_favorite': bool(row['is_favorite']),
        'created_at': row['created_at'],
        'ports': ports
    }
    
    return jsonify(device)

@app.route('/api/devices/<int:device_id>', methods=['PUT'])
def update_device(device_id):
    """更新设备信息"""
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    
    updates = []
    params = []
    
    if 'notes' in data:
        updates.append('notes = ?')
        params.append(data['notes'])
    
    if 'is_favorite' in data:
        updates.append('is_favorite = ?')
        params.append(1 if data['is_favorite'] else 0)
    
    if updates:
        params.append(device_id)
        cursor.execute(f'UPDATE devices SET {", ".join(updates)} WHERE id = ?', params)
        db.commit()
    
    return jsonify({'success': True})

@app.route('/api/devices/<int:device_id>/scan', methods=['POST'])
def scan_device_ports(device_id):
    """扫描设备端口"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
    row = cursor.fetchone()
    
    if not row:
        return jsonify({'error': '设备不存在'}), 404
    
    ip = row['ip_address']
    
    # 获取端口列表
    settings = db.execute('SELECT value FROM settings WHERE key = ?', ('scan_ports',)).fetchone()
    if settings:
        port_list = [int(p.strip()) for p in settings[0].split(',') if p.strip().isdigit()]
    else:
        port_list = [22, 80, 443, 3389, 8080, 8443, 21, 23, 25, 53, 110, 143, 3306, 5432, 6379, 27017]
    
    success = scan_ports(device_id, ip, port_list)
    
    if success:
        return jsonify({'success': True, 'message': f'已扫描 {len(port_list)} 个端口'})
    else:
        return jsonify({'success': False, 'message': '扫描失败'}), 500

@app.route('/api/devices/scan', methods=['POST'])
def trigger_scan():
    """触发网络扫描"""
    network_info = get_local_network()
    cidr = network_info['cidr']
    
    devices, count, duration = scan_network(cidr)
    
    return jsonify({
        'success': True,
        'devices_found': count,
        'duration': round(duration, 2),
        'message': f'扫描完成，发现 {count} 台设备，耗时 {duration:.2f} 秒'
    })

@app.route('/api/ports/<int:port_id>', methods=['PUT'])
def update_port(port_id):
    """更新端口备注"""
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    
    if 'notes' in data:
        cursor.execute('UPDATE ports SET notes = ? WHERE id = ?', (data['notes'], port_id))
        db.commit()
    
    return jsonify({'success': True})

@app.route('/api/ports/<int:port_id>', methods=['DELETE'])
def delete_port(port_id):
    """删除端口记录"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('DELETE FROM ports WHERE id = ?', (port_id,))
    db.commit()
    
    return jsonify({'success': True})

@app.route('/api/logs', methods=['GET'])
def get_scan_logs():
    """获取扫描日志"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM scan_logs ORDER BY created_at DESC LIMIT 20')
    rows = cursor.fetchall()
    
    logs = []
    for row in rows:
        logs.append({
            'id': row['id'],
            'devices_found': row['devices_found'],
            'scan_type': row['scan_type'],
            'duration': row['duration'],
            'created_at': row['created_at']
        })
    
    return jsonify(logs)

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取设置"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM settings')
    rows = cursor.fetchall()
    
    settings = {}
    for row in rows:
        settings[row['key']] = row['value']
    
    return jsonify(settings)

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    """更新设置"""
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    
    for key, value in data.items():
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    
    db.commit()
    
    return jsonify({'success': True})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    db = get_db()
    cursor = db.cursor()
    
    total = cursor.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
    online = cursor.execute('SELECT COUNT(*) FROM devices WHERE is_online = 1').fetchone()[0]
    favorites = cursor.execute('SELECT COUNT(*) FROM devices WHERE is_favorite = 1').fetchone()[0]
    ports = cursor.execute('SELECT COUNT(*) FROM ports WHERE status = "open"').fetchone()[0]
    
    return jsonify({
        'total_devices': total,
        'online_devices': online,
        'favorite_devices': favorites,
        'open_ports': ports
    })

# ============ 自动扫描 ============
scheduler = BackgroundScheduler()

def auto_scan():
    """自动扫描任务"""
    print("执行自动扫描...")
    try:
        network_info = get_local_network()
        scan_network(network_info['cidr'])
    except Exception as e:
        print(f"自动扫描失败: {e}")

def setup_auto_scan(enabled, interval_minutes):
    """设置自动扫描"""
    if scheduler.running:
        scheduler.shutdown()
    
    if enabled and interval_minutes > 0:
        scheduler.add_job(
            func=auto_scan,
            trigger='interval',
            minutes=interval_minutes,
            id='auto_scan'
        )
        scheduler.start()

# 确保 data 目录存在
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)

# 初始化
init_db()

if __name__ == '__main__':
    print('========================================')
    print('  局域网设备管理器已启动')
    print('  访问地址: http://localhost:5000')
    print('========================================')
    
    # 启动Web服务器
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
