# 固鼎固定资产管理系统 - 外网部署指南

## 快速部署（推荐使用 Docker）

### 前置条件
- 安装 Docker 和 Docker Compose
- 服务器有公网 IP
- 防火墙开放端口 5200 和 5201

### 部署步骤

```bash
# 1. 克隆项目到服务器
git clone <仓库地址> guding
cd guding

# 2. 修改生产环境配置（重要！）
# 编辑 backend/.env，修改 JWT_SECRET 和数据库密码
vi backend/.env

# 3. 启动服务
docker-compose up -d

# 4. 查看状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | `http://服务器IP:5201` |
| 后端 API 文档 | `http://服务器IP:5200/docs` |
| 默认账号 | `admin` / `admin123` |

---

## 手动部署（无 Docker）

### 1. 安装依赖

```bash
# 后端
cd backend
pip install uv
uv sync

# 前端
cd frontend
npm install
```

### 2. 配置数据库

确保 MySQL 已安装并运行，然后执行初始化：

```bash
cd backend
uv run python init_db.py
```

### 3. 启动服务

```bash
# 启动后端（后台运行）
cd backend
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 5200 &

# 启动前端（开发模式）
cd frontend
nohup npm run dev &
```

---

## 生产环境优化

### 1. 构建前端静态文件

```bash
cd frontend
npm run build
```

构建产物在 `frontend/dist` 目录，可用 Nginx 托管。

### 2. Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:5200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 3. 配置 HTTPS

```bash
# 安装 certbot
apt install certbot python3-certbot-nginx

# 获取证书
certbot --nginx -d your-domain.com
```

---

## 防火墙配置

### Windows 防火墙

```powershell
# 开放端口
netsh advfirewall firewall add rule name="Guding Backend" dir=in action=allow protocol=TCP localport=5200
netsh advfirewall firewall add rule name="Guding Frontend" dir=in action=allow protocol=TCP localport=5201
```

### Linux 防火墙

```bash
# UFW
sudo ufw allow 5200/tcp
sudo ufw allow 5201/tcp
sudo ufw reload

# 或 firewalld
sudo firewall-cmd --permanent --add-port=5200/tcp
sudo firewall-cmd --permanent --add-port=5201/tcp
sudo firewall-cmd --reload
```

### 云服务器安全组

在云服务器控制台（阿里云/腾讯云/华为云等）的安全组中添加入站规则：

| 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|
| TCP | 5200 | 0.0.0.0/0 | 后端 API |
| TCP | 5201 | 0.0.0.0/0 | 前端页面 |

---

## 常见问题

### Q: 外网无法访问？

1. 检查防火墙是否开放端口
2. 检查云服务器安全组配置
3. 确认服务已启动：`docker-compose ps` 或 `netstat -tlnp | grep 5200`

### Q: API 请求失败？

1. 检查后端日志：`docker-compose logs backend`
2. 确认数据库连接正常
3. 检查 JWT_SECRET 是否已修改

### Q: 如何修改端口？

编辑 `docker-compose.yml`，修改 `ports` 配置：

```yaml
ports:
  - "新端口:5200"  # 后端
  - "新端口:80"    # 前端
```

然后重新启动：`docker-compose up -d`
