# Azure Migration Quick Start Guide

This is a condensed version of the full migration guide. Use this for quick reference during implementation.

## Prerequisites

- Azure account with active subscription
- Azure CLI installed (`az --version` to check)
- Python 3.8+ installed
- Access to current lab PC setup

## Step 1: Create Azure Resources (30 minutes)

### 1.1 Login to Azure
```bash
az login
az account set --subscription "<your-subscription-id>"
```

### 1.2 Create Resource Group
```bash
az group create --name experiment-tracking-prod --location eastus
```

### 1.3 Create Azure SQL Database
```bash
# Create SQL Server
az sql server create \
  --name experiment-tracking-sql \
  --resource-group experiment-tracking-prod \
  --location eastus \
  --admin-user sqladmin \
  --admin-password "<strong-password>"

# Create Database
az sql db create \
  --server experiment-tracking-sql \
  --resource-group experiment-tracking-prod \
  --name experiments \
  --service-objective S0 \
  --backup-storage-redundancy Local

# Allow Azure Services (for App Service access)
az sql server firewall-rule create \
  --resource-group experiment-tracking-prod \
  --server experiment-tracking-sql \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### 1.4 Create Azure Storage Account
```bash
az storage account create \
  --name experimenttrackingstorage \
  --resource-group experiment-tracking-prod \
  --location eastus \
  --sku Standard_LRS

# Create container
az storage container create \
  --name uploads \
  --account-name experimenttrackingstorage \
  --auth-mode login
```

### 1.5 Get Storage Connection String
```bash
az storage account show-connection-string \
  --name experimenttrackingstorage \
  --resource-group experiment-tracking-prod \
  --query connectionString \
  --output tsv
```
**Save this connection string!**

### 1.6 Create Azure App Service
```bash
# Create App Service Plan
az appservice plan create \
  --name experiment-tracking-plan \
  --resource-group experiment-tracking-prod \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --name experiment-tracking-app \
  --resource-group experiment-tracking-prod \
  --plan experiment-tracking-plan \
  --runtime "PYTHON:3.11"
```

## Step 2: Database Migration (2-3 hours)

### 2.1 Export SQLite Data
On your lab PC:
```bash
sqlite3 experiments.db .dump > experiments_backup.sql
```

### 2.2 Install PostgreSQL Tools (if using PostgreSQL)
```bash
# Windows (using Chocolatey)
choco install postgresql

# Or download from: https://www.postgresql.org/download/windows/
```

### 2.3 Convert and Import Data
```bash
# Get connection string from Azure Portal
# Format: postgresql://user:password@server.database.windows.net:5432/experiments

# Convert SQLite dump (manual editing may be required)
# Then import:
psql "postgresql://user:password@server.database.windows.net:5432/experiments" < experiments_backup.sql
```

### 2.4 Run Alembic Migrations
```bash
# Update .env with new DATABASE_URL
DATABASE_URL=postgresql://user:password@server.database.windows.net:5432/experiments

# Run migrations
alembic upgrade head
```

## Step 3: Configure Azure AD Authentication (1-2 hours)

### 3.1 Register App in Azure AD
1. Go to Azure Portal → Azure Active Directory → App registrations
2. Click "New registration"
3. Name: "Experiment Tracking App"
4. Supported account types: "Accounts in this organizational directory only"
5. Redirect URI: `https://experiment-tracking-app.azurewebsites.net/.auth/login/aad/callback`
6. Click "Register"

### 3.2 Get Client Credentials
1. Go to "Certificates & secrets"
2. Create new client secret
3. **Save the secret value immediately** (you can't see it again!)
4. Note the Client ID and Tenant ID

### 3.3 Install MSAL Library
```bash
pip install msal
```

Add to `requirements.txt`:
```
msal>=1.24.0
```

## Step 4: Update Configuration Files

### 4.1 Update `.env` (Local Development)
```bash
# Database
DATABASE_URL=postgresql://user:password@server.database.windows.net:5432/experiments

# Storage
STORAGE_TYPE=azure
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER=uploads

# Authentication
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
```

### 4.2 Configure Azure App Service Environment Variables
```bash
az webapp config appsettings set \
  --name experiment-tracking-app \
  --resource-group experiment-tracking-prod \
  --settings \
    DATABASE_URL="postgresql://user:password@server.database.windows.net:5432/experiments" \
    STORAGE_TYPE="azure" \
    AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..." \
    AZURE_STORAGE_CONTAINER="uploads" \
    AZURE_CLIENT_ID="your-client-id" \
    AZURE_CLIENT_SECRET="your-client-secret" \
    AZURE_TENANT_ID="your-tenant-id"
```

## Step 5: Deploy Application

### 5.1 Create Startup Script
Create `startup.sh`:
```bash
#!/bin/bash
streamlit run app.py --server.port=8000 --server.address=0.0.0.0
```

Make it executable:
```bash
chmod +x startup.sh
```

### 5.2 Configure App Service Startup
```bash
az webapp config set \
  --name experiment-tracking-app \
  --resource-group experiment-tracking-prod \
  --startup-file "startup.sh"
```

### 5.3 Deploy via Git (Recommended)
```bash
# Add Azure remote
az webapp deployment source config-local-git \
  --name experiment-tracking-app \
  --resource-group experiment-tracking-prod

# Get deployment URL
az webapp deployment source show \
  --name experiment-tracking-app \
  --resource-group experiment-tracking-prod \
  --query url \
  --output tsv

# Add as git remote and push
git remote add azure <deployment-url>
git push azure main
```

### 5.4 Alternative: Deploy via ZIP
```bash
# Create deployment package
zip -r deploy.zip . -x "*.git*" "*.venv*" "__pycache__/*" "*.db" "*.pyc"

# Deploy
az webapp deployment source config-zip \
  --resource-group experiment-tracking-prod \
  --name experiment-tracking-app \
  --src deploy.zip
```

## Step 6: Migrate Files to Azure Blob Storage

### 6.1 Create Migration Script
Create `scripts/migrate_files_to_azure.py`:
```python
import os
from pathlib import Path
from utils.storage import save_file
from config.storage import get_storage_config

def migrate_files():
    """Migrate local files to Azure Blob Storage."""
    config = get_storage_config()
    if config["type"] != "azure":
        print("Storage type is not Azure. Update STORAGE_TYPE in .env")
        return
    
    uploads_dir = Path("uploads")
    for file_path in uploads_dir.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(uploads_dir)
            folder = str(relative_path.parent)
            file_name = relative_path.name
            
            print(f"Uploading {relative_path}...")
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            blob_url = save_file(file_data, file_name, folder, create_backup=False)
            print(f"  → {blob_url}")

if __name__ == "__main__":
    migrate_files()
```

### 6.2 Run Migration
```bash
python scripts/migrate_files_to_azure.py
```

## Step 7: Test Everything

### 7.1 Test Database Connection
```bash
python -c "from database import SessionLocal; db = SessionLocal(); print('Connected!')"
```

### 7.2 Test File Upload
- Log into the app
- Upload a test file
- Verify it appears in Azure Blob Storage

### 7.3 Test Authentication
- Log out
- Log in with Azure AD
- Verify user can access app

## Step 8: Monitor and Optimize

### 8.1 Enable Application Insights
```bash
az monitor app-insights component create \
  --app experiment-tracking-insights \
  --location eastus \
  --resource-group experiment-tracking-prod

# Link to App Service
az monitor app-insights component connect-webapp \
  --app experiment-tracking-insights \
  --resource-group experiment-tracking-prod \
  --web-app experiment-tracking-app
```

### 8.2 Set Up Alerts
- Go to Azure Portal → App Service → Alerts
- Create alerts for:
  - High response time
  - High error rate
  - Low availability

## Common Issues & Solutions

### Issue: Database Connection Fails
**Solution:**
- Check firewall rules in Azure SQL Database
- Verify connection string format
- Ensure Azure services are allowed

### Issue: Files Not Uploading
**Solution:**
- Verify `AZURE_STORAGE_CONNECTION_STRING` is correct
- Check container name matches
- Verify storage account is accessible

### Issue: App Won't Start
**Solution:**
- Check Application Logs: `az webapp log tail --name experiment-tracking-app --resource-group experiment-tracking-prod`
- Verify startup command is correct
- Check Python version matches runtime

### Issue: Authentication Not Working
**Solution:**
- Verify redirect URI matches exactly
- Check client ID and secret are correct
- Ensure app registration is in same tenant

## Cost Optimization Tips

1. **Use Basic Tier Initially**
   - App Service B1: ~$13/month
   - SQL Database S0: ~$15/month
   - Storage: Pay per GB

2. **Enable Auto-Shutdown** (for dev/test)
   - Reduces costs when not in use

3. **Use Reserved Instances** (for production)
   - 1-3 year commitments save 30-50%

4. **Monitor Usage**
   - Set up billing alerts
   - Review costs monthly

## Next Steps After Migration

1. ✅ Update DNS (if using custom domain)
2. ✅ Set up automated backups
3. ✅ Configure monitoring and alerts
4. ✅ Document new access procedures
5. ✅ Train users on new login method
6. ✅ Decommission old lab PC setup (after verification period)

## Rollback Plan

If issues occur:
1. Keep lab PC running during transition
2. Switch `DATABASE_URL` back to SQLite temporarily
3. Switch `STORAGE_TYPE` back to `local`
4. Investigate issues in staging environment
5. Re-attempt migration after fixes

## Support Resources

- **Azure Documentation**: https://docs.microsoft.com/azure/
- **Streamlit on Azure**: https://docs.streamlit.io/deploy/azure
- **Azure Support**: https://azure.microsoft.com/support/
