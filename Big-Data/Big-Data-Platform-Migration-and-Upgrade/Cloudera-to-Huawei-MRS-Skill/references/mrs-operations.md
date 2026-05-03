# MRS Operations

## MRS Cluster Access

### SSH Access

```bash
# Standard SSH (if port 22 is open)
ssh -p 22 root@<eip_or_internal_ip>

# MRS default SSH port
ssh -p 9022 root@<eip_or_internal_ip>
```

Default credentials are set during cluster creation and stored in:
- `.secrets/mrs-<cluster-name>.env` (local)
- MRS Manager UI (remote)

### MRS Manager UI

- URL: `https://<master_floating_ip>:28860`
- Default admin user: `admin`
- Password: set during cluster creation

### Client Environment

Always source the client environment before running any Hadoop command:

```bash
su - omm -c 'source /opt/Bigdata/client/bigdata_env && <command>'
```

The client environment sets:
- `JAVA_HOME`
- `HADOOP_HOME`, `HADOOP_CONF_DIR`
- `HIVE_HOME`, `SPARK_HOME`
- PATH for all Hadoop ecosystem binaries

## Key Paths on MRS Master

| Path | Description |
| --- | --- |
| `/opt/Bigdata/client/` | Client installation root |
| `/opt/Bigdata/client/bigdata_env` | Environment setup script |
| `/opt/Bigdata/client/Hive/` | Hive client |
| `/opt/Bigdata/client/Hive/Beeline/bin/beeline` | beeline binary |
| `/opt/Bigdata/client/Hive/config/hive-site.xml` | Hive configuration |
| `/opt/Bigdata/client/Spark/spark/` | Spark client |
| `/opt/Bigdata/client/Spark/spark/bin/spark-sql` | spark-sql binary |
| `/opt/Bigdata/client/Spark/spark/conf/` | Spark configuration |
| `/opt/Bigdata/` | MRS service installation root |
| `/usr/bin/obsutil` | OBS utility |

## Service Users

| User | Purpose |
| --- | --- |
| `omm` | Hadoop service account; owns all Hadoop processes |
| `hdfs` | HDFS superuser |
| `hive` | Hive service account |
| `spark` | Spark service account |
| `root` | OS administrator; can sudo to any user |

**Always run Hadoop/Hive/Spark commands as `omm`:**

```bash
su - omm -c 'source /opt/Bigdata/client/bigdata_env && hdfs dfs -ls /'
su - omm -c 'source /opt/Bigdata/client/bigdata_env && beeline -u "jdbc:hive2://<ip>:10000" -e "SHOW DATABASES;"'
su - omm -c 'source /opt/Bigdata/client/bigdata_env && spark-sql --master yarn -e "SHOW DATABASES;"'
```

## obsutil Operations

### Configuration

```bash
obsutil config -i=<ak> -k=<sk> -e=obs.<region>.myhuaweicloud.com
```

### Common Operations

```bash
# List buckets
obsutil ls

# Create bucket
obsutil mb obs://<bucket> -location=<region>

# List bucket contents
obsutil ls obs://<bucket>/<prefix>/ -limit=100 -s

# Upload directory (recursive, force, parallel)
obsutil cp /local/dir obs://<bucket>/<prefix>/ -flat -r -f -j=4 -p=4

# Download directory
obsutil cp obs://<bucket>/<prefix>/ /local/dir -flat -r -f -j=4 -p=4

# Check bucket size
obsutil ls obs://<bucket> -limit=0 -s
```

## MRS Cluster Lifecycle

### Check Cluster Status

```python
from huaweicloudsdkmrs.v1.mrs_client import MrsClient
from huaweicloudsdkmrs.v1.model.list_clusters_request import ListClustersRequest

req = ListClustersRequest()
resp = client.list_clusters(req)
for c in resp.clusters:
    print(f"{c.cluster_name}: {c.cluster_state}")
```

### Scale Cluster

Add or remove Task nodes (Core nodes cannot be removed):

```python
# Through MRS Manager UI or SDK
# MRS supports auto-scaling policies
```

### Delete Cluster

```python
from huaweicloudsdkmrs.v1.model.delete_cluster_request import DeleteClusterRequest
req = DeleteClusterRequest(cluster_id=<cluster_id>)
resp = client.delete_cluster(req)
```

**Warning:** Deleting a cluster deletes all HDFS data. OBS data is preserved.

## Monitoring

### Spark UI

- URL: `http://<master_ip>:18080` (Spark History Server)
- Or access through MRS Manager UI

### YARN ResourceManager

- URL: `http://<master_ip>:8088`
- View running applications, queue status, resource usage

### HDFS NameNode

- URL: `http://<master_ip>:9870`
- View HDFS capacity, file system status

### MRS Manager Alerts

- MRS Manager UI -> Alerts
- Configure alert thresholds and notification channels
