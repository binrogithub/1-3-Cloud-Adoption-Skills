# 食堂订餐系统交付与运维手册

## 1. 部署结果概览
- 应用访问地址：`http://18.191.159.217/`
- 订单管理页：`http://18.191.159.217/admin/orders`
- 健康检查：`http://18.191.159.217/health`
- EC2 实例：`i-0d31fa15334e0b294`（`us-east-2`）
- RDS 实例：`canteen-ordering-mysql`（MySQL 8.4.8，`db.t3.micro`）

## 2. 系统架构
- Web：Flask + Gunicorn
- 反向代理：Nginx（80端口）
- 数据库：AWS RDS MySQL（私网访问）
- 进程守护：systemd

## 3. 目录与配置
- 应用目录：`/opt/canteen-ordering`
- 环境变量：`/etc/canteen-ordering.env`
- systemd 服务：`/etc/systemd/system/canteen-ordering.service`
- Nginx 站点：`/etc/nginx/sites-available/canteen-ordering`

## 4. 日常操作指引（应用使用）
### 4.1 用户下单
1. 打开首页 `http://18.191.159.217/`。
2. 在菜单中填写菜品数量。
3. 输入姓名、手机号（必填），取餐时间与备注（可选）。
4. 点击“确认下单”。
5. 页面返回订单号即表示提交成功。

### 4.2 食堂管理查看订单
1. 打开 `http://18.191.159.217/admin/orders`。
2. 查看最近 100 条订单，包括：下单人、手机号、菜品明细、金额、状态与备注。

## 5. 运维指引
### 5.1 服务管理
```bash
sudo systemctl status canteen-ordering
sudo systemctl restart canteen-ordering
sudo systemctl stop canteen-ordering
sudo systemctl start canteen-ordering

sudo systemctl status nginx
sudo systemctl restart nginx
```

### 5.2 日志排查
```bash
sudo journalctl -u canteen-ordering -f
sudo journalctl -u canteen-ordering -n 200 --no-pager
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

### 5.3 健康检查
```bash
curl -sS http://127.0.0.1/health
curl -sS http://18.191.159.217/health
```

### 5.4 配置修改
- 修改数据库连接、密钥：编辑 `/etc/canteen-ordering.env`。
- 修改后重启应用：
```bash
sudo systemctl restart canteen-ordering
```

### 5.5 应用更新发布
1. 将新代码上传到 `/opt/canteen-ordering`。
2. 如依赖变化，执行：
```bash
/opt/canteen-ordering/venv/bin/pip install -r /opt/canteen-ordering/requirements.txt
```
3. 重启服务：
```bash
sudo systemctl restart canteen-ordering
sudo systemctl restart nginx
```
4. 验证：
```bash
curl -sS http://127.0.0.1/health
```

### 5.6 迁移后自动恢复脚本（一键）
- 脚本位置：`deploy/restart_after_migration.sh`
- 推荐执行：
```bash
sudo bash deploy/restart_after_migration.sh --public-health-url http://<新服务器公网IP>/health
```
- 若新机器未装 MySQL 客户端，可自动安装：
```bash
sudo bash deploy/restart_after_migration.sh --install-mysql-client
```
- 如需跳过依赖安装或数据库检查：
```bash
sudo bash deploy/restart_after_migration.sh --skip-pip --skip-db-check
```

### 5.7 数据库备份与恢复（RDS）
- 建议开启自动快照（当前保留 1 天，可调大）。
- 手工创建快照：
```bash
aws rds create-db-snapshot \
  --region us-east-2 \
  --db-instance-identifier canteen-ordering-mysql \
  --db-snapshot-identifier canteen-ordering-manual-$(date +%Y%m%d%H%M)
```
- 恢复时在 AWS 控制台或 CLI 从快照创建新实例，验证后切换应用 `DB_HOST`。

### 5.8 安全建议（上线前）
1. 将 EC2 的 22 端口从 `0.0.0.0/0` 收敛到固定运维出口 IP。
2. 为站点配置 HTTPS（ACM + ALB，或 Nginx + Let's Encrypt）。
3. 定期轮换数据库密码，并同步更新 `/etc/canteen-ordering.env`。
4. 为 `/admin/orders` 增加登录认证（当前为内网/轻量测试用途页面）。

## 6. 关键资源清单
- EC2 安全组：`sg-00ef415b4c61ffe1a`（放行 `22`、`80`）
- RDS 安全组：`sg-0244ff1e5f830a46f`（仅允许来自 EC2 安全组的 `3306`）
- RDS 子网组：`canteen-ordering-subnet-group`

## 7. 故障快速定位
### 现象：网页无法访问
1. `sudo systemctl status nginx canteen-ordering`
2. `curl http://127.0.0.1:8000/health`
3. 检查安全组是否放行 `80`。

### 现象：下单失败
1. 查看应用日志：`journalctl -u canteen-ordering -n 200 --no-pager`
2. 校验数据库连通：检查 `/etc/canteen-ordering.env` 中 `DB_HOST/DB_USER/DB_PASSWORD`。
3. 在 AWS 控制台确认 RDS 状态 `available`。

### 现象：数据库连接超时
1. 检查 RDS 安全组入站规则是否允许 EC2 安全组访问 `3306`。
2. 检查 EC2 与 RDS 是否在同一 VPC。
3. 检查 RDS endpoint 是否变更。
