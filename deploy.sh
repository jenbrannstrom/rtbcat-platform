#!/bin/bash
# Cat-Scan One-Click Deployment Script
# Usage: ./deploy.sh [aws|destroy]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/terraform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_banner() {
    echo ""
    echo "╔═══════════════════════════════════════════╗"
    echo "║        Cat-Scan QPS Optimizer             ║"
    echo "║        One-Click AWS Deployment           ║"
    echo "╚═══════════════════════════════════════════╝"
    echo ""
}

check_requirements() {
    echo -e "${YELLOW}Checking requirements...${NC}"

    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        echo -e "${RED}Error: Terraform not installed${NC}"
        echo "Install: https://developer.hashicorp.com/terraform/downloads"
        exit 1
    fi

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}Error: AWS CLI not installed${NC}"
        echo "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}Error: AWS credentials not configured${NC}"
        echo "Run: aws configure"
        exit 1
    fi

    echo -e "${GREEN}All requirements met!${NC}"
}

deploy() {
    print_banner
    check_requirements

    echo -e "${YELLOW}Initializing Terraform...${NC}"
    cd "$TERRAFORM_DIR"
    terraform init

    echo ""
    echo -e "${YELLOW}Planning deployment...${NC}"
    terraform plan -out=tfplan

    echo ""
    echo -e "${YELLOW}This will create:${NC}"
    echo "  - EC2 t3.small instance (2GB RAM, ~\$17/month)"
    echo "  - Elastic IP (stable address)"
    echo "  - S3 bucket (CSV archival)"
    echo "  - Security groups"
    echo ""
    read -p "Deploy Cat-Scan to AWS? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deploying...${NC}"
        terraform apply tfplan

        echo ""
        echo -e "${GREEN}═══════════════════════════════════════════${NC}"
        echo -e "${GREEN}        Deployment Complete!               ${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════${NC}"
        echo ""
        terraform output
    else
        echo "Deployment cancelled."
        rm -f tfplan
    fi
}

destroy() {
    print_banner

    echo -e "${RED}WARNING: This will destroy all Cat-Scan resources!${NC}"
    echo "This includes:"
    echo "  - EC2 instance and all data on it"
    echo "  - S3 bucket and all stored CSVs"
    echo "  - Elastic IP"
    echo ""
    read -p "Are you sure? Type 'destroy' to confirm: " -r
    echo ""

    if [[ $REPLY == "destroy" ]]; then
        cd "$TERRAFORM_DIR"
        terraform destroy
    else
        echo "Destruction cancelled."
    fi
}

show_status() {
    cd "$TERRAFORM_DIR"
    if [ -f "terraform.tfstate" ]; then
        echo -e "${GREEN}Current deployment:${NC}"
        terraform output
    else
        echo "No deployment found."
    fi
}

show_help() {
    print_banner
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  aws      Deploy Cat-Scan to AWS (default)"
    echo "  status   Show current deployment status"
    echo "  destroy  Destroy all AWS resources"
    echo "  help     Show this help message"
    echo ""
    echo "Prerequisites:"
    echo "  1. Install Terraform: https://developer.hashicorp.com/terraform/downloads"
    echo "  2. Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    echo "  3. Configure AWS: aws configure"
    echo ""
    echo "After deployment:"
    echo "  1. Wait 2-3 minutes for containers to start"
    echo "  2. Access dashboard at the URL shown in output"
    echo "  3. Upload Google credentials via Setup page"
    echo "  4. Import your first CSV"
}

# Main
case "${1:-aws}" in
    aws|deploy)
        deploy
        ;;
    destroy)
        destroy
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
