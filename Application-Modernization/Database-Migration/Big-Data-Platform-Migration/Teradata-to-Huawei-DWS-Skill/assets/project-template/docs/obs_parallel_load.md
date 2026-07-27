# OBS 并行装载模板

当前 demo 默认使用客户端 `\copy` 装载 CSV，适合小数据量演示。生产迁移应优先采用：

1. Teradata 分区/批次导出。
2. 上传到 OBS。
3. DWS 从 OBS/GDS/外表并行导入。
4. 按表、分区、批次校验行数和指标。

## 配置

```bash
cp config/obs.env.example config/obs.env
vi config/obs.env
```

`config/obs.env` 不应提交到版本库。

## 上传导出文件并生成 DWS 装载 SQL 模板

```bash
./scripts/prepare_obs_parallel_load.sh
```

该命令会：

- 上传 `data/export/*.csv` 到 `obs://$OBS_BUCKET/$OBS_PREFIX/`
- 生成 `sql/dws/08_load_from_obs.generated.sql`

## 注意

`sql/dws/08_load_from_obs.generated.sql` 是模板，不默认执行。不同 DWS 版本和安全策略对 OBS 装载语法、AK/SK、委托/agency、外表能力有差异。执行前必须按目标 DWS 版本复核。

