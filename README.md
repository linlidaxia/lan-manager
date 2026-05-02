# 🌐 局域网设备管理器 (LAN Device Manager)

一个可以在 Docker 中部署的局域网硬件设备搜索和管理 Web 应用。

![Docker](https://img.shields.io/docker/pulls/lan-manager) ![License](https://img.shields.io/github/license/lan-manager)

## ✨ 功能特性

- 🔍 **自动发现设备** - 通过 ARP 扫描发现局域网内所有在线设备
- 📊 **设备信息记录** - 记录 MAC 地址、设备类型、厂商、在线状态、延迟等
- 🌐 **端口扫描** - 检测设备开放的端口和服务
- 📝 **服务备注** - 为每个端口添加自定义服务说明
- ⭐ **收藏设备** - 标记重要设备
- 🔄 **自动扫描** - 支持定时自动扫描
- 📋 **扫描日志** - 记录扫描历史

## 🚀 快速开始

### 前置要求

- Docker
- Docker Compose (可选)

### 安装步骤

#### 方式一：使用 Docker Compose (推荐)

```bash
# 1. 克隆或下载项目
git clone <repo-url> lan-manager
cd lan-manager

# 2. 构建并启动容器
docker-compose up -d

# 3. 访问 Web 界面
# 浏览器打开 http://localhost:5000
```

#### 方式二：使用 Docker 命令

```bash
# 构建镜像
docker build -t lan-manager .

# 运行容器 (需要使用 host 网络模式以访问局域网)
docker run -d --name lan-manager \
  --network host \
  -v $(pwd)/data:/data \
  -e DEBUG=False \
  lan-manager

# 访问 http://<你的IP>:5000
```

#### 方式三：本地运行 (开发模式)

```bash
# 安装依赖
pip install -r requirements.txt

# 安装系统依赖 (nmap)
# Ubuntu/Debian:
sudo apt install nmap iputils-ping net-tools

# CentOS/RHEL:
sudo yum install nmap iputils net-tools

# 启动应用
python app.py

# 访问 http://localhost:5000
```

## 📖 使用说明

### 1. 扫描网络

- 首次启动会自动扫描局域网
- 点击「扫描网络」按钮手动触发扫描
- 在「设置」页面开启自动扫描

### 2. 查看设备

- 设备列表显示所有发现的设备
- 可搜索 IP、MAC、主机名、厂商
- 勾选「仅在线」过滤离线设备
- 点击设备行查看详情

### 3. 端口扫描

- 在设备详情页点击「扫描端口」
- 可在「设置」页面自定义要扫描的端口
- 支持常用端口、Web服务、数据库、Windows等多种模板

### 4. 服务备注

- 端口扫描后，可为每个端口添加服务说明
- 例如：80 端口可备注为「Web 管理界面」

## 🐳 Docker 部署注意事项

### 重要提示

由于网络扫描需要访问宿主机的网络，使用 Docker 部署时请使用 `network_mode: host`，这样容器可以直接使用宿主机的网络适配器扫描局域网。

### 权限问题

如果遇到权限问题，可尝试：

```bash
# 方案1: 使用 --privileged
docker run -d --name lan-manager \
  --privileged \
  --network host \
  -v $(pwd)/data:/data \
  lan-manager

# 方案2: 添加网络管理能力
docker run -d --name lan-manager \
  --cap-add=NET_ADMIN \
  --network host \
  -v $(pwd)/data:/data \
  lan-manager
```

### 数据持久化

数据库文件保存在 `/data/devices.db`，可通过 volume 挂载到宿主机：

```yaml
volumes:
  - ./data:/data
```

## ⚙️ 配置说明

### 默认扫描端口

```
22,80,443,3389,8080,8443,21,23,25,53,110,143,3306,5432,6379,27017
```

### 常用端口模板

| 模板 | 端口 |
|------|------|
| 常用端口 | 22, 80, 443, 21, 23, 25, 53, 110, 143, 3389, 3306, 27017 |
| Web 服务 | 80, 443, 8080, 8443, 88, 8000, 8888, 3000, 5000 |
| 数据库 | 3306, 5432, 27017, 6379, 9200, 11211, 1521 |
| Windows | 135, 139, 445, 3389, 5985, 5986, 8530, 8531 |

## 🔧 技术栈

- **后端**: Python 3.11 + Flask
- **前端**: Vue 3 + TailwindCSS
- **数据库**: SQLite
- **网络扫描**: nmap
- **容器**: Docker

## 📁 项目结构

```
lan-manager/
├── app.py                 # Flask 后端主程序
├── requirements.txt       # Python 依赖
├── Dockerfile            # Docker 镜像配置
├── docker-compose.yml    # Docker Compose 配置
├── templates/
│   └── index.html       # 前端页面 (Vue + TailwindCSS)
├── SPEC.md              # 规格说明文档
└── README.md            # 本文件
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License