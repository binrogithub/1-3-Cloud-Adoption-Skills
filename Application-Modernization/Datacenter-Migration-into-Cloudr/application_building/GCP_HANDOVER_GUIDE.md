# 食堂订餐系统（GCP）交付与运维手册

更新时间：2026-06-27（UTC）

## 1. 部署结果（已完成）
- 实例：`instance-20260627-200301`（`us-central1-c`）
- 公网地址：`http://104.198.60.131/`
- 订单管理页：`http://104.198.60.131/admin/orders`
- 健康检查：`http://104.198.60.131/health`
- 数据库实例：`mysql-canteen-77775452`
- MySQL 连接：`35.223.228.162:3306`（SSL CA 验证）

验收结果：
- 公网首页 `HTTP 200`
- 公网健康检查返回 `{"status":"ok"}`
- 通过 `/api/orders` 成功创建测试订单（`order_id=1`）
- 管理页可见测试订单

## 2. 服务器部署结构
- 应用目录：`/opt/canteen-ordering`
- Python 虚拟环境：`/opt/canteen-ordering/venv`
- 环境变量：`/etc/canteen-ordering.env`
- systemd 服务：`/etc/systemd/system/canteen-ordering.service`
- Nginx 站点：`/etc/nginx/sites-available/canteen-ordering`

## 3. 应用操作指引
### 3.1 用户下单
1. 打开 `http://104.198.60.131/`。
2. 选择菜品数量。
3. 填写姓名、手机号（必填）。
4. 可选填写取餐时间和备注。
5. 点击提交，返回订单号即成功。

### 3.2 管理员查看订单
1. 打开 `http://104.198.60.131/admin/orders`。
2. 查看最近 100 条订单及订单明细。

## 4. 系统维护指引
### 4.1 服务管理
```bash
sudo systemctl status canteen-ordering
sudo systemctl restart canteen-ordering
sudo systemctl stop canteen-ordering
sudo systemctl start canteen-ordering

sudo systemctl status nginx
sudo systemctl restart nginx
```

### 4.2 日志排查
```bash
sudo journalctl -u canteen-ordering -n 200 --no-pager
sudo journalctl -u canteen-ordering -f
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

### 4.3 健康检查
```bash
curl -sS http://127.0.0.1/health
curl -sS http://104.198.60.131/health
```

### 4.4 修改配置
配置文件：`/etc/canteen-ordering.env`

改完后执行：
```bash
sudo systemctl daemon-reload
sudo systemctl restart canteen-ordering
sudo systemctl restart nginx
```

### 4.5 发布新版本
```bash
cd /opt/canteen-ordering
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart canteen-ordering
sudo systemctl restart nginx
```

### 4.6 一键恢复脚本
```bash
sudo bash /opt/canteen-ordering/deploy/restart_after_migration.sh \
  --public-health-url http://104.198.60.131/health
```

## 5. 数据库连接与安全建议
- 应用使用账号已切换为独立业务账号（非 root），凭据保存于：
  - `/etc/canteen-ordering.env`
- SSL CA 路径：
  - `/opt/canteen-ordering/server-ca.pem`
- 建议：
1. 定期轮换数据库密码（更新 `/etc/canteen-ordering.env` 后重启服务）。
2. 定期确认 Cloud SQL 备份策略有效。
3. 生产建议增加 HTTPS（负载均衡证书或 Nginx 证书）。

## 6. 常见故障处理
### 6.1 页面打不开
1. `sudo systemctl status nginx canteen-ordering`
2. `curl -I http://127.0.0.1/`
3. 检查 GCP 防火墙 `tcp:80` 规则。

### 6.2 页面 502
1. `sudo journalctl -u canteen-ordering -n 200 --no-pager`
2. 检查 `/etc/canteen-ordering.env` 的 DB 配置与 SSL 路径。
3. 检查数据库连通：
```bash
sudo bash -lc 'source /etc/canteen-ordering.env; MYSQL_PWD="$DB_PASSWORD" mysql --ssl-mode=VERIFY_CA --ssl-ca="$DB_SSL_CA" -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" -e "SELECT 1;"'
```

### 6.3 下单失败
1. 查看应用日志中是否有 SQL 异常。
2. 检查 `menu_items` 是否有可用菜品。
3. 确认数据库实例处于可用状态。
