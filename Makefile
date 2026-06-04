SHELL := /bin/bash

TF_DIR=infra/terraform

.PHONY: help tf-init tf-plan tf-apply tf-destroy lint controlled-proof controlled-proof-report

help:
	@echo "Targets:"
	@echo "  tf-init      Terraform init"
	@echo "  tf-plan      Terraform plan (expects prod.tfvars in $(TF_DIR))"
	@echo "  tf-apply     Terraform apply (expects prod.tfvars in $(TF_DIR))"
	@echo "  tf-destroy   Terraform destroy (careful!)"
	@echo "  controlled-proof  Seed runtime, boot backend, probe controlled endpoints, and run the controlled RFQ proof"
	@echo "  controlled-proof-report  Print the saved controlled proof summary"

tf-init:
	cd $(TF_DIR) && terraform init

tf-plan:
	cd $(TF_DIR) && terraform plan -var-file=prod.tfvars

tf-apply:
	cd $(TF_DIR) && terraform apply -var-file=prod.tfvars

tf-destroy:
	cd $(TF_DIR) && terraform destroy -var-file=prod.tfvars

controlled-proof:
	bash scripts/run_controlled_shared_runtime_proof.sh

controlled-proof-report:
	python3 scripts/show_controlled_proof_report.py
