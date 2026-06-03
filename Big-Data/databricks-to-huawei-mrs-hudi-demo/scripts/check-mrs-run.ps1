param(
  [Parameter(Mandatory=$true)]
  [string]$ClusterId,
  [string]$DemoRoot = "C:\Users\Matebook\Documents\Codex\2026-06-02\files-mentioned-by-the-user-databricks\outputs\huawei-dli-hudi-demo"
)

$ErrorActionPreference = "Stop"
Set-Location $DemoRoot
. .\scripts\14_select_huawei_auth.ps1 -ForceFallback

@"
import json, os
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkmrs.v1 import MrsClient as C1, ShowClusterDetailsRequest
from huaweicloudsdkmrs.v1.region.mrs_region import MrsRegion as R1
from huaweicloudsdkmrs.v2 import MrsClient as C2, ShowJobExeListNewRequest
from huaweicloudsdkmrs.v2.region.mrs_region import MrsRegion as R2

cluster_id = "$ClusterId"
cred = BasicCredentials(os.environ["HUAWEICLOUD_ACCESS_KEY"], os.environ["HUAWEICLOUD_SECRET_KEY"], os.environ["HUAWEICLOUD_PROJECT_ID"])
if os.environ.get("HUAWEICLOUD_SECURITY_TOKEN"):
    cred.with_security_token(os.environ["HUAWEICLOUD_SECURITY_TOKEN"])

client1 = C1.new_builder().with_credentials(cred).with_region(R1.value_of("la-south-2")).build()
client2 = C2.new_builder().with_credentials(cred).with_region(R2.value_of("la-south-2")).build()

out = {}
try:
    detail = client1.show_cluster_details(ShowClusterDetailsRequest(cluster_id=cluster_id)).to_json_object().get("cluster", {})
    out["cluster"] = {k: detail.get(k) for k in ["clusterId", "clusterName", "clusterState", "stageDesc", "stagePercent", "mrsManagerFinish", "duration", "fee", "errorInfo", "errorMessage"]}
except Exception as exc:
    out["cluster_error"] = {"class": exc.__class__.__name__, "status_code": getattr(exc, "status_code", None), "error_code": getattr(exc, "error_code", None), "error_msg": getattr(exc, "error_msg", None)}

try:
    out["jobs"] = client2.show_job_exe_list_new(ShowJobExeListNewRequest(cluster_id=cluster_id, limit="20", offset="1")).to_json_object()
except Exception as exc:
    out["jobs_error"] = {"class": exc.__class__.__name__, "status_code": getattr(exc, "status_code", None), "error_code": getattr(exc, "error_code", None), "error_msg": getattr(exc, "error_msg", None)}

print(json.dumps(out, indent=2, default=str))
"@ | python -
