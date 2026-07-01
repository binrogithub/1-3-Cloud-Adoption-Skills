# dev environment

Copy the modular template files into this folder or reference modules using relative paths.

Recommended command flow:

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out tfplan
terraform apply tfplan
```
