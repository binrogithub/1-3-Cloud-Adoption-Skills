# Alloy 配置渲染

AutoOps 不修改 Alloy 源码或运行时配置。管理员在部署主机上为已登记的
ServiceProfile 生成项目自己的日志采集片段：

```bash
python3 scripts/render-alloy-profile.py \
  --profile config/service-profiles/<profile>.json \
  --loki-url https://loki.example.internal \
  --output /etc/alloy/autoops-<service>.alloy
```

渲染器只接受 active profile 中的已登记 journal/file source，写入 application、
environment、target、scope_id 和 service 标签。Loki 的 tenant/token 由 Alloy
部署环境提供，不写入生成文件。已有 Loki source 只表示查询端点，不会被重复渲染为
第二个采集器。
