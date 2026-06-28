# 食堂订餐网页系统

技术栈：Flask + MySQL(RDS) + Gunicorn + Nginx

## 功能
- 用户网页点餐
- 菜单展示
- 订单创建入库
- 管理页查看最近 100 条订单

## 本地运行（需要 MySQL）
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_NAME=canteen_ordering
export DB_USER=root
export DB_PASSWORD=your_password
python app.py
```

访问：
- 点餐页面：`/`
- 订单管理：`/admin/orders`
- 健康检查：`/health`

## 生产部署关键文件
- `deploy/canteen-ordering.service`：systemd 服务
- `deploy/nginx-canteen.conf`：Nginx 反向代理
- `deploy/app.env.example`：应用环境变量示例
