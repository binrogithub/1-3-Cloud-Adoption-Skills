==================================================================================================
  LOCAL INFRASTRUCTURE (KIND)                                          CLOUD INFRASTRUCTURE (CCE)
==================================================================================================

  [ CONTROL PLANE ]
  +---------------------------------------------------+               +---------------------------------------------------+
  | Control-Plane Node (Docker Container)             |               | MANAGED CONTROL PLANE (Managed by Huawei)         |
  | - Runs kube-apiserver, etcd, scheduler             |    MIGRATES   | - No node visible to the user                      |
  | - Managed explicitly by you in Docker [2]          |  ---------->  | - Free, highly available and fault-tolerant        |
  | - Topology: 1 node [2]                            |               |   (you don't pay for this plane) [17]              |
  +---------------------------------------------------+               +---------------------------------------------------+

              |                                                                               |
              v                                                                               v

  [ WORKER NODES ]
  +---------------------------------------------------+               +---------------------------------------------------+
  | Worker Node 1 (Docker Container)                  |               | Worker Node 1 (ECS Virtual Machine)               |
  | - Runs kubelet, kube-proxy, containerd            |    MIGRATES   | - Flavor: ac8.large.2 (2vCPU / 4GB RAM) [17]      |
  | - Storage: Host local disk [4]                    |  ---------->  | - Billing: Pay-per-use (on demand) [17]           |
  +---------------------------------------------------+               +---------------------------------------------------+
  +---------------------------------------------------+               +---------------------------------------------------+
  | Worker Node 2 (Docker Container)                  |               | Worker Node 2 (ECS Virtual Machine)               |
  | - Topology mirrors CCE: 2 workers [2]             |    MIGRATES   | - Access: SSH keypair for root access             |
  +---------------------------------------------------+               +---------------------------------------------------+

              |                                                                               |
              v                                                                               v

  [ NETWORK AND CLUSTER ACCESS ]
  +---------------------------------------------------+               +---------------------------------------------------+
  | Network: Docker Bridge Network (Local internal)   |               | Network: VPC & Subnet in Huawei Cloud (Isolated)  |
  | API Server: localhost / port-mapping in Docker     |    MIGRATES   | API Server: Public EIP (Elastic IP) [17]          |
  | - kubectl points to localhost                      |  ---------->  | - kubectl points to CCE public IP                 |
  +---------------------------------------------------+               +---------------------------------------------------+

              |                                                                               |
              v                                                                               v

  [ NETWORK AND APPLICATION ACCESS (INGRESS) ]
  +---------------------------------------------------+               +---------------------------------------------------+
  | Ingress Controller: Nginx (DaemonSet/NodePort)    |               | Ingress Controller: Nginx (DaemonSet/LoadBalancer)|
  | DNS: Local /etc/hosts modification [5]            |    MIGRATES   | Traffic entry: ELB (Elastic Load Balancer)        |
  | Traffic: Localhost -> NodePort -> Ingress -> Pod  |  ---------->  | DNS: Public DNS / Real hostname                    |
  | No external load balancer                         |               | Traffic: Internet -> ELB -> Ingress -> Pod [18]   |
  +---------------------------------------------------+               +---------------------------------------------------+

              |                                                                               |
              v                                                                               v

  [ PERSISTENT STORAGE AND REGISTRY ]
  +---------------------------------------------------+               +---------------------------------------------------+
  | Provisioner: Rancher local-path [4]               |               | Provisioner: CSI (EVS / SFS)                      |
  | Disk: Host filesystem (Docker Vol)                |    MIGRATES   | Disk: EVS (Elastic Volume Service) attached to ECS|
  | PVC Size: 1Gi (Local) [17]                        |  ---------->  | PVC Size: 10Gi minimum (EVS) [17]                 |
  +---------------------------------------------------+               +---------------------------------------------------+
  +---------------------------------------------------+               +---------------------------------------------------+
  | Registry: Docker Hub                              |               | Registry: SWR (Software Repository for Container) |
  | Images: Direct pull (nginx:1.27-alpine) [7]       |    MIGRATES   | Images: Push to tenant SWR beforehand [17]        |
  +---------------------------------------------------+               +---------------------------------------------------+
==================================================================================================
