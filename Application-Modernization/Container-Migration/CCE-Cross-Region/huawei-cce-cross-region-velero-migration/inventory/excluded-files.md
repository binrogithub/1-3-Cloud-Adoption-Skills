# Excluded Files

The following patterns are excluded from the delivery package:

- .git/
- node_modules/
- .venv/
- venv/
- __pycache__/
- .playwright-mcp/
- .env (real)
- .env.local
- .env.production
- *.pem
- *.key
- id_rsa
- id_ed25519
- kubeconfig
- terraform.tfstate
- terraform.tfstate.*
- *.bak
- *.backup
-/out/
- DRS_*.json (API skeletons with real data)
- IAM_*.json (API skeletons with real data)
- VPC_*.json (API skeletons with real data)
- credentials-*
- session.json
- *.log
