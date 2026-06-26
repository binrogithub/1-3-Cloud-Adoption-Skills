# VM Migration Tool (Huawei Cloud)

一个可重复使用的 VM 迁移工具，统一入口为 `scripts/run_vm_migrate.sh`，核心执行引擎为 `scripts/mgc_migrate.py`。

## 1. 准备配置

```bash
cp config/vm_migrate.env.example config/vm_migrate.env
# 编辑 config/vm_migrate.env，至少填写：
# HC_AK / HC_SK / SOURCE_SERVER_ID / SOURCE_REGION / TARGET_REGION
# TARGET_IMAGE_ID / TARGET_ADMIN_PASSWORD
```

## 2. 执行迁移

```bash
bash scripts/run_vm_migrate.sh
# 或指定配置文件
bash scripts/run_vm_migrate.sh /path/to/your.env
```

## 3. 输出结果

默认输出：`out/migration_result.json`

脚本会按配置自动选择 SMS 或 rsync（或 SMS 失败后回退 rsync）。

## 4. 复用方式

后续迁移只需要替换 `config/vm_migrate.env` 中的源 VM、目标区域和镜像参数，重复执行即可。
