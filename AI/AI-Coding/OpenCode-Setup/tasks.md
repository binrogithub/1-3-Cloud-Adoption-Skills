1. Install WSL
2. Install Terraform, Open Code, KooCLI, Docker Engine
3. Configure KooCLI
4. Configure Open Code
5. Configure MCP Servers for Open Code (Terraform MCP and hcloud MCP)

## Install WSL
`wsl --install -d Ubuntu`

## Install Terraform, Open Code, Docker Engine, KooCLI

### Terraform:

`sudo apt-get update && sudo apt-get install -y gnupg software-properties-common`

`wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null`

`echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list`

`sudo apt update`

`sudo apt install terraform`

### Docker Engine (recommended over docker desktop for enterprises):

`sudo apt update`

`sudo apt install ca-certificates curl`

`sudo install -m 0755 -d /etc/apt/keyrings`

`sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc`

`sudo chmod a+r /etc/apt/keyrings/docker.asc`

```
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

`sudo apt update`

`sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`

#### docker rootless:

`sudo groupadd docker`

`sudo usermod -aG docker $USER`

### KooCLI

`curl -LO "https://ap-southeast-3-hwcloudcli.obs.ap-southeast-3.myhuaweicloud.com/cli/latest/huaweicloud-cli-linux-amd64.tar.gz"`

`tar -zxvf huaweicloud-cli-linux-amd64.tar.gz`

`sudo mv $(pwd)/hcloud /usr/local/bin/`

`hcloud auto-complete on`

### Open Code

`curl -fsSL https://opencode.ai/install | bash`

## Configure KooCLI
1. Get AK/SK from Huawei Cloud Console
2. Login in KooCLI using AK/SK

`hcloud configure init`

https://console-intl.huaweicloud.com/apiexplorer/#/endpoint/OBS
`hcloud obs hcloud obs config -i=ak -k=sk -e=https://obs.<REGION>.myhuaweicloud.com`

## Configure Open Code
1. Subscribe to Huawei Cloud MaaS models
2. Get API key of MaaS
3. Get endpoint of MaaS
4. Create `~/.opencode/opencode.json` file


```
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "huawei-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Huawei Cloud MaaS",
      "options": {
        "baseURL": "MAAS_BASE_URL"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek-V4-Flash",
          "limit": {
            "context": 1048576,
            "output": 131072
          }
        },
        "deepseek-v3.2": {
          "name": "DeepSeek-V3.2",
          "limit": {
            "context": 163840,
            "output": 32768
          }
        },
        "deepseek-v3.1-terminus": {
          "name": "DeepSeek-V3.1",
          "limit": {
            "context": 131072,
            "output": 32768
          }
        },
        "DeepSeek-V3": {
          "name": "DeepSeek-V3",
          "limit": {
            "context": 131072,
            "output": 131072
          }
        },
        "deepseek-r1-250528": {
          "name": "DeepSeek-R1-0528",
          "limit": {
            "context": 131072,
            "output": 32768
          }
        },
        "glm-5": {
          "name": "GLM-5",
          "limit": {
            "context": 202752,
            "output": 65536
          }
        },
        "glm-5.1": {
          "name": "GLM-5.1",
          "limit": {
            "context": 202752,
            "output": 131072
          }
        }
      }
    }
  }
}
```

### Configure MCP servers for OpenCode

#### Terraform MCP server

1. Obtain HCP Terraform token, required only for newer versions of Terraform MCP https://app.terraform.io/login
2. Add Terraform MCP to Open Code

```
"mcp": {
    "terraform": {
      "type": "local",
      "command": ["docker", "run", "-i", "--rm", "-e", "TFE_ADDRESS", "-e", "TFE_TOKEN", "hashicorp/terraform-mcp-server:0.5.1"],
      "enabled": true,
      "environment": {
        "TFE_ADDRESS": "https://app.terraform.io",
        "TFE_TOKEN": "TERRAFORM_TOKEN"
      }
    }
  }
```

#### hcloud mcp server (optional)
I developed this MCP server just to be a wrapper around KooCLI terminal tool, it's very simple but it is easier for the agents to navigate mcp tools, instead of trying to execute bash commands.

`pip install -e .`

```
"mcp": {
    "hcloud": {
      "type": "local",
      "command": ["hcloud-mcp"],
      "enabled": true
    }
  }
```

## Demo
1. Testing hcloud
2. Deploying a infrastrucure


```
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "terraform": {
      "type": "local",
      "command": ["docker", "run", "-i", "--rm", "-e", "TFE_ADDRESS", "-e", "TFE_TOKEN", "hashicorp/terraform-mcp-server:0.5.1"],
      "enabled": true,
      "environment": {
        "TFE_ADDRESS": "https://app.terraform.io",
        "TFE_TOKEN": "YOUR_TFE_TOKEN"
      }
    },
    "hcloud": {
      "type": "local",
      "command": ["hcloud-mcp"],
      "enabled": true
    }
  },
  "provider": {
    "huawei-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Huawei Cloud MaaS",
      "options": {
        "baseURL": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
        "apiKey": "YOUR_MAAS_API_KEY"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek-V4-Flash",
          "limit": {
            "context": 1048576,
            "output": 131072
          }
        },
        "deepseek-v3.2": {
          "name": "DeepSeek-V3.2",
          "limit": {
            "context": 163840,
            "output": 32768
          }
        },
        "deepseek-v3.1-terminus": {
          "name": "DeepSeek-V3.1",
          "limit": {
            "context": 131072,
            "output": 32768
          }
        },
        "DeepSeek-V3": {
          "name": "DeepSeek-V3",
          "limit": {
            "context": 131072,
            "output": 131072
          }
        },
        "deepseek-r1-250528": {
          "name": "DeepSeek-R1-0528",
          "limit": {
            "context": 131072,
            "output": 32768
          }
        },
        "glm-5": {
          "name": "GLM-5",
          "limit": {
            "context": 202752,
            "output": 65536
          }
        },
        "glm-5.1": {
          "name": "GLM-5.1",
          "limit": {
            "context": 202752,
            "output": 131072
          }
        }
      }
    }
  }
}
```