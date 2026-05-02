# 局域网硬件设备管理Web程序规格说明

## 1. 项目概述

- **项目名称**: LAN Device Manager (局域网设备管理器)
- **项目类型**: Web全栈应用 (Docker部署)
- **核心功能**: 扫描、监控和管理局域网内的硬件设备，支持端口扫描和服务备注
- **目标用户**: 网络管理员、家庭用户、极客

## 2. 技术栈

- **后端**: Python 3.11 + Flask + SQLite
- **前端**: Vue 3 (CDN) + TailwindCSS
- **网络扫描**: nmap (系统依赖)
- **容器**: Docker + docker-compose

## 3. 功能列表

### 3.1 设备扫描
- [x] 自动检测本机局域网IP段
- [x] ARP扫描发现在线设备
- [x] 记录MAC地址、IP地址、主机名
- [x] 计算访问延迟 (ping)
- [x] 设备类型识别 (通过MAC厂商前缀)
- [x] 手动触发扫描 / 自动定时扫描

### 3.2 设备列表
- [x] 表格展示所有设备
- [x] 显示在线/离线状态 (实时刷新)
- [x] 显示延迟、最后在线时间
- [x] 搜索过滤设备
- [x] 标记设备 (收藏/重要)

### 3.3 设备详情
- [x] 设备基本信息 (IP, MAC, 主机名, 类型)
- [x] 端口扫描 (常用端口: 22, 80, 443, 3389, 8080等)
- [x] 显示开放端口及服务
- [x] 接口服务备注功能

### 3.4 接口管理
- [x] 为每个端口添加服务描述/备注
- [x] 预设常用服务模板 (HTTP, SSH, RDP, FTP等)
- [x] 自定义备注

### 3.5 数据持久化
- [x] SQLite数据库存储
- [x] 设备历史记录
- [x] 扫描日志

## 4. 页面结构

1. **首页/设备列表** - 展示所有设备卡片/表格
2. **设备详情页** - 端口扫描 + 接口备注
3. **设置页** - 扫描参数、定时任务配置

## 5. API设计

```
GET  /api/devices           - 获取所有设备
POST /api/devices/scan      - 触发扫描
GET  /api/devices/<id>      - 获取设备详情
GET  /api/devices/<id>/ports - 端口扫描
PUT  /api/devices/<id>      - 更新设备备注
GET  /api/ports/<device_id> - 获取设备端口列表
POST /api/ports             - 添加端口备注
PUT  /api/ports/<id>        - 更新端口备注
DELETE /api/ports/<id>      - 删除端口备注
GET  /api/settings          - 获取设置
PUT  /api/settings          - 更新设置
```

## 6. 数据库表设计

### devices
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| ip_address | VARCHAR(45) | IP地址 |
| mac_address | VARCHAR(17) | MAC地址 |
| hostname | VARCHAR(255) | 主机名 |
| device_type | VARCHAR(50) | 设备类型 |
| vendor | VARCHAR(100) | 厂商 |
| is_online | BOOLEAN | 在线状态 |
| latency | FLOAT | 延迟(ms) |
| last_seen | DATETIME | 最后在线 |
| notes | TEXT | 设备备注 |
| is_favorite | BOOLEAN | 收藏 |
| created_at | DATETIME | 创建时间 |

### ports
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| device_id | INTEGER | 设备ID |
| port | INTEGER | 端口号 |
| protocol | VARCHAR(10) | 协议 |
| service | VARCHAR(50) | 服务名 |
| status | VARCHAR(20) | 状态 |
| notes | TEXT | 服务备注 |
| created_at | DATETIME | 创建时间 |

### scan_logs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| devices_found | INTEGER | 发现设备数 |
| scan_type | VARCHAR(20) | 扫描类型 |
| duration | FLOAT | 耗时(秒) |
| created_at | DATETIME | 扫描时间 |

## 7. UI/UX设计

- **主题**: 深色科技风 (Dark Tech)
- **主色调**: 墨蓝 (#0f172a) + 青色强调 (#06b6d4)
- **布局**: 侧边栏 + 主内容区
- **动画**: 流畅的过渡效果
- **响应式**: 支持桌面端

## 8. Docker配置

- 基础镜像: python:3.11-slim
- 安装: nmap, iputils-ping
- 端口: 5000
- 数据卷: 持久化SQLite数据库