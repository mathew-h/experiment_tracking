# Azure Migration Guide for Experiment Tracking Webapp

This guide is designed for a developer who is comfortable with Python but new to the "DevOps" and "Production" side of things. We will move through this step-by-step, starting with setting up the "home" for your app, then moving the data, and finally deploying the code.

---

### Phase 1: The Azure Foundation (Days 1–2)

Before moving code, you need to create the "containers" where your app and data will live.

1.  **Create a Resource Group:**
    *   Log into the [Azure Portal](https://portal.azure.com).
    *   Search for "Resource Groups" -> **Create**.
    *   Name it `experiment-tracking-rg`. Choose a region close to you (e.g., *East US* or *West Europe*).
    *   *Think of this as a folder that holds everything related to this project.*

2.  **Create the Database (PostgreSQL):**
    *   Search for "Azure Database for PostgreSQL flexible servers" -> **Create**.
    *   **Server name:** `experiment-db-server`
    *   **Workload type:** Smallest/Development (Burstable, B1ms).
    *   **Authentication:** Choose "PostgreSQL authentication only" for now (it's easier for beginners). Set an admin username and password. **Save these!**
    *   **Firewall:** Check the box "Allow public access from any Azure service" (this allows your Web App to talk to the DB).

3.  **Create Storage:**
    *   Search for "Storage accounts" -> **Create**.
    *   **Name:** `experimentstorage[randomletters]` (must be unique globally).
    *   **Redundancy:** Change to "Locally-redundant storage (LRS)" to save money.
    *   Once created, go to **Containers** (left sidebar) -> click **+ Container** -> name it `uploads`.

---

### Phase 2: Database Migration (Days 3–5)

Since you are moving from a file (SQLite) to a real server (PostgreSQL), you need to "pump" the data from one to the other.

1.  **Install a Database Tool:** Download [DBeaver](https://dbeaver.io/) (Free). It allows you to see your SQLite and Postgres tables side-by-side.
2.  **The Migration Script:** Because Postgres is "strict" about data types, the easiest way for a Python developer to migrate is using a small script.
    *   Create a file `migrate_db.py`:
    ```python
    import sqlite3
    import pandas as pd
    from sqlalchemy import create_engine

    # 1. Connect to local SQLite
    sqlite_conn = sqlite3.connect('experiments.db')

    # 2. Connect to Azure Postgres
    # Format: postgresql://user:password@host:port/database
    pg_engine = create_engine('postgresql://admin:password@your-server.postgres.database.azure.com:5432/postgres')

    # 3. List your tables
    tables = ['experiments', 'users', 'results'] # Add your table names here

    for table in tables:
        df = pd.read_sql(f'SELECT * FROM {table}', sqlite_conn)
        # This creates the table in Postgres and uploads data
        df.to_sql(table, pg_engine, if_exists='replace', index=False)
        print(f"Migrated {table}")
    ```
3.  **Run Alembic:** Once the data is moved, run your migrations (`alembic upgrade head`) against the new Postgres URL to ensure all constraints/indexes are applied.

---

### Phase 3: Storage Migration (Day 6)

You need to move your `uploads/` folder to Azure Blob Storage.

1.  **Get your Connection String:** In the Azure Portal, go to your Storage Account -> **Access Keys** -> Click "Show" on Connection String. Copy it.
2.  **Upload existing files:**
    *   Install [Azure Storage Explorer](https://azure.microsoft.com/en-us/products/storage/storage-explorer/) (a desktop app like File Explorer for Azure).
    *   Log in and simply drag-and-drop your local `uploads/` folder into the `uploads` container you created in Phase 1.

---

### Phase 4: Authentication Setup (Days 7–10)

Moving from Firebase to Microsoft (Entra ID) is the most "technical" part.

1.  **Register the App:**
    *   Azure Portal -> **Microsoft Entra ID** -> **App registrations** -> **New registration**.
    *   Name: `Experiment Tracker Webapp`.
    *   Redirect URI: Select "Web" and type `https://your-app-name.azurewebsites.net`.
2.  **Get Secrets:**
    *   Copy the **Application (client) ID** and **Directory (tenant) ID**.
    *   Go to **Certificates & secrets** -> **New client secret**. Copy the Value immediately (it disappears forever once you leave the page).
3.  **Update Streamlit Code:**
    Use a library like `msal` or a wrapper. A common pattern for Streamlit is using the [msal-streamlit-authentication](https://pypi.org/project/msal-streamlit-authentication/) component which handles the login button for you.

---

### Phase 5: Preparing for Production (Days 11–13)

Azure App Service needs a few specific files to know how to run Streamlit.

1.  **Create `requirements.txt`:** Ensure `psycopg2-binary` (for Postgres) and `azure-storage-blob` are inside.
2.  **Create `startup.sh`:** (In your root folder)
    ```bash
    python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0
    ```
3.  **The `.deployment` file:**
    ```ini
    [config]
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
    ```

---

### Phase 6: Deploying the App (Day 14)

1.  **Create the Web App:**
    *   Search "App Services" -> **Create** -> **Web App**.
    *   **Runtime stack:** Python 3.11.
    *   **Plan:** Basic B1 (required for "Always On").
2.  **Set Environment Variables:**
    *   In the Web App page -> **Environment variables** (left side).
    *   Add all your keys from your `.env` file here:
        *   `DATABASE_URL`
        *   `AZURE_STORAGE_CONNECTION_STRING`
        *   `AZURE_CLIENT_ID`, etc.
3.  **Deploy via GitHub (Recommended):**
    *   Go to **Deployment Center** in the App Service.
    *   Link your GitHub account and select your repository.
    *   Azure will automatically create a "GitHub Action" that deploys your code every time you `git push`.

---

### Phase 7: The "Pain Prevention" Settings (Crucial!)

Once the app is running, you **must** do these three things or the app will feel broken:

1.  **Enable ARR Affinity:**
    *   App Service -> **Configuration** -> **General settings**.
    *   Set **ARR Affinity** to **On**. (This ensures that if a user is mid-session, they stay connected to the same server "instance").
2.  **Enable Always On:**
    *   In the same **General settings** tab, set **Always On** to **On**. (This prevents the app from "sleeping" and taking 30 seconds to wake up when a user visits).
3.  **Set Startup Command:**
    *   In the same **General settings** tab, find "Startup Command" and enter:
    *   `bash startup.sh`

---

### How to Test Your Work

1.  **Check Logs:** If the app doesn't load, go to **Log Stream** in the App Service sidebar. It will show you the Python errors just like your local terminal does.
2.  **Verify DB:** Use DBeaver to connect to the Azure Postgres DB and see if new experiments are being saved.
3.  **Check Storage:** Upload a file in the app, then go to the Azure Portal to see if it appeared in the Blob Container.

### Summary of Costs
*   **App Service (B1):** ~$13/mo
*   **Postgres (B1ms):** ~$15/mo
*   **Storage:** ~$1-2/mo (for 30GB)
*   **Total:** **~$30/month** for a professional, enterprise-grade setup.


## Executive Summary


**Is Azure the Right Path?** ✅ **YES**

Azure is an excellent choice for your migration because:
- **Native Microsoft Integration**: Seamless integration with Entra ID (Azure AD), Office 365, and SharePoint
- **Single Sign-On**: Users can authenticate with existing Microsoft accounts
- **Enterprise Security**: Built-in security features, compliance certifications, and data encryption
- **Managed Services**: Reduces operational overhead compared to self-hosting
- **Cost-Effective**: Pay-as-you-go pricing with free tier options
- **Your Code is Already Ready**: Azure Blob Storage support is already implemented in your codebase

### Practical Nuances That Prevent Pain

For a small team (5–10) in a Microsoft-centric environment, this architecture is a "Goldilocks" solution: enterprise reliability without excessive complexity. The items below are the key nuances that make the implementation go smoothly in practice:

1. **Streamlit Session Affinity (ARR Affinity)**  
   Streamlit is stateful. Azure App Service uses a load balancer, so requests can bounce across instances and break session state.  
   **Action**: Enable **ARR Affinity** (Session Affinity) in App Service.

2. **SQLite → PostgreSQL (Type-Strict Migration)**  
   SQLite is type-loose; PostgreSQL/Azure SQL are strict. Direct `.dump` imports often fail.  
   **Action**: Use **Azure Database for PostgreSQL Flexible Server** and migrate with a Python script (SQLAlchemy/pandas) or a tool like `pgloader`.

3. **Managed Identity + DefaultAzureCredential**  
   Avoid secrets in env vars when possible. Managed Identities let your App Service talk to DB and Blob Storage without credentials.  
   **Action**: Use `DefaultAzureCredential` from `azure-identity` and configure Managed Identity access.

4. **Cold Starts (Always On)**  
   Streamlit cold starts can look like downtime.  
   **Action**: Enable **Always On** in App Service (available on Basic tier or higher).

## Complexity Assessment

### Overall Complexity: **MODERATE** (3-4 weeks for a beginner)

**Breakdown:**
- **Database Migration**: Medium complexity (SQLite → Azure Database for PostgreSQL)
- **Authentication Migration**: Medium complexity (Firebase → Azure AD/Entra ID)
- **File Storage**: **Already Done** ✅ (Azure Blob Storage code exists)
- **App Deployment**: Low-Medium complexity (Streamlit → Azure App Service)
- **Configuration**: Low complexity (environment variables)

### Why It's Manageable:
1. Your codebase already supports Azure Blob Storage
2. SQLAlchemy makes database switching straightforward
3. Streamlit deployment to Azure is well-documented
4. Most changes are configuration-based, not code rewrites

## Current Architecture

```
┌─────────────────┐
│  Lab PC (Local) │
│                 │
│  ┌───────────┐  │
│  │ Streamlit │  │
│  │   App     │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ SQLite DB │  │
│  │(local)   │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ Local FS  │  │
│  │ (uploads) │  │
│  └───────────┘  │
│                 │
│  ┌───────────┐  │
│  │ Firebase  │  │
│  │   Auth    │  │
│  └───────────┘  │
└─────────────────┘
        │
    Tailscale VPN
        │
    Users Access
```

## Target Azure Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Azure Cloud                          │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Azure App Service (Streamlit)            │  │
│  │  - Auto-scaling                                 │  │
│  │  - HTTPS/SSL                                    │  │
│  │  - Always available                             │  │
│  └──────────────┬─────────────────────────────────┘  │
│                 │                                      │
│    ┌────────────┼────────────┐                        │
│    │            │            │                        │
│  ┌─▼──┐    ┌───▼───┐   ┌───▼────┐                    │
│  │SQL │    │ Blob  │   │ Entra  │                    │
│  │DB  │    │Storage│   │   ID   │                    │
│  └────┘    └───────┘   └────────┘                    │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │         Azure Key Vault (Secrets)                │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                    │
            Internet (HTTPS)
                    │
            Authenticated Users
```

## Migration Components

### 1. Database Migration (SQLite → Azure Database for PostgreSQL)

**Current State:**
- SQLite database (`experiments.db`)
- Local file-based storage
- No concurrent write limitations

**Target State:**
- Azure Database for PostgreSQL (Flexible Server)
- Cloud-hosted, secure, backed up automatically
- Supports concurrent connections

**Migration Steps:**
1. Create Azure Database for PostgreSQL (Flexible Server)
2. Migrate data using a Python script (SQLAlchemy/pandas) or `pgloader`
3. Update `DATABASE_URL` environment variable
4. Run Alembic migrations on new database
5. Test thoroughly

**Estimated Time:** 1-2 days

**Code Changes Required:**
- ✅ Minimal - just update `DATABASE_URL` environment variable
- Your SQLAlchemy models are database-agnostic
- Alembic migrations will work as-is

**Security:**
- Azure Database for PostgreSQL includes:
  - Encryption at rest
  - Encryption in transit (TLS)
  - Firewall rules (IP whitelisting)
  - Azure AD authentication
  - Automated backups (7-35 days retention)

### 2. Authentication Migration (Firebase → Azure AD/Entra ID)

**Current State:**
- Firebase Authentication
- Custom user management

**Target State:**
- Azure AD/Entra ID authentication
- Single Sign-On with Office 365
- Integrated user management

**Migration Steps:**
1. Register app in Azure AD
2. Configure authentication endpoints
3. Update authentication code to use Azure AD
4. Migrate existing users (if needed)
5. Test authentication flow

**Estimated Time:** 2-3 days

**Code Changes Required:**
- Create new authentication module (`auth/azure_ad.py`)
- Update `auth_components.py` to use Azure AD
- Remove Firebase dependencies (optional, can keep for transition)

**Security Benefits:**
- Users authenticate with existing Microsoft accounts
- No separate username/password management
- Enterprise-grade security policies
- Multi-factor authentication support
- Conditional access policies

### 3. File Storage (Already Implemented! ✅)

**Current State:**
- Local file system storage
- Files in `uploads/` directory

**Target State:**
- Azure Blob Storage
- **Code already exists** in `utils/storage.py`

**Migration Steps:**
1. Create Azure Storage Account
2. Create blob container
3. Prefer Managed Identity authentication (see Security section below)
4. If using connection strings, update environment variables:
   ```
   STORAGE_TYPE=azure
   AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>
   AZURE_STORAGE_CONTAINER=<container-name>
   ```
5. Migrate existing files (one-time script)
6. Test file uploads/downloads

**Estimated Time:** 1 day

**Code Changes Required:**
- ✅ **NONE** - Azure support already implemented!
- Just update configuration

**Security:**
- Private containers by default
- Shared Access Signatures (SAS) for temporary access
- Encryption at rest
- Access control via Azure AD

### 4. Application Deployment (Streamlit → Azure App Service)

**Current State:**
- Running on local lab PC
- Accessible via Tailscale VPN

**Target State:**
- Azure App Service
- Public HTTPS endpoint
- Auto-scaling
- Always available

**Migration Steps:**
1. Create Azure App Service (Linux)
2. Configure deployment (GitHub Actions or Azure DevOps)
3. Set environment variables in Azure Portal
4. Deploy application
5. Configure custom domain (optional)
6. Set up monitoring and alerts

**Estimated Time:** 2-3 days

**Code Changes Required:**
- Create deployment configuration files
- Update any hardcoded paths
- Configure startup command

**Security:**
- HTTPS enforced
- Managed SSL certificates
- Network isolation options
- Application Insights for monitoring

## Step-by-Step Migration Plan

### Phase 1: Preparation (Week 1)

1. **Set up Azure Account**
   - Create Azure subscription (or use existing)
   - Set up billing alerts
   - Create resource group: `experiment-tracking-prod`

2. **Create Azure Resources**
   ```bash
   # Azure Database for PostgreSQL (Flexible Server)
   az postgres flexible-server create --name <server-name> --resource-group <rg-name> --location <location> --tier Burstable --sku-name B1ms
   
   # Azure Storage Account
   az storage account create --name <storage-name> --resource-group <rg-name> --location <location>
   az storage container create --name uploads --account-name <storage-name>
   

   # Azure App Service
   az appservice plan create --name <plan-name> --resource-group <rg-name> --sku B1 --is-linux
   az webapp create --name <app-name> --resource-group <rg-name> --plan <plan-name> --runtime "PYTHON:3.11"
   ```

3. **Backup Current System**
   - Full database backup
   - Export all uploaded files
   - Document current configuration

### Phase 2: Database Migration (Week 1-2)

1. **Create Azure Database for PostgreSQL**
   - Use Azure Portal or CLI
   - Configure firewall rules
   - Set up Azure AD admin

2. **Migrate Data (Type-Safe)**
   - Use a Python script with SQLAlchemy/pandas to read SQLite and write to Postgres
   - Or use a tool like `pgloader`
   - Avoid direct `.dump` imports to prevent type issues

3. **Run Alembic Migrations**
   - Apply migrations to the new database

4. **Test Database Connection**
   - Update local `.env` temporarily
   - Test all database operations
   - Verify data integrity

### Phase 3: Storage Migration (Week 2)

1. **Configure Azure Blob Storage**
   - Get connection string from Azure Portal
   - Update `config/storage.py` if needed (add Azure config)

2. **Migrate Files**
   - Create migration script to upload existing files
   - Update database records with new blob URLs
   - Verify file access

3. **Test File Operations**
   - Upload new files
   - Download existing files
   - Delete files

### Phase 4: Authentication Migration (Week 2-3)

1. **Register App in Azure AD**
   - Go to Azure Portal → Azure Active Directory → App registrations
   - Create new registration
   - Configure redirect URIs
   - Get client ID and secret

2. **Update Authentication Code**
   - Install `msal` library: `pip install msal`
   - Create `auth/azure_ad.py` module
   - Update `frontend/components/auth_components.py`

3. **Test Authentication**
   - Test login flow
   - Test user permissions
   - Migrate existing users if needed

### Phase 5: Application Deployment (Week 3)

1. **Prepare Deployment**
   - Create `requirements.txt` (already exists)
   - Create `.deployment` file for Azure
   - Create `startup.sh` script

2. **Deploy to Azure**
   - Use Azure Portal or GitHub Actions
   - Configure environment variables
   - Set startup command: `streamlit run app.py --server.port=8000 --server.address=0.0.0.0 --server.enableCORS=false`

3. **Configure App Service**
   - Enable **ARR Affinity** (Session Affinity) for Streamlit statefulness
   - Enable **Always On** to avoid cold starts
   - Set up custom domain (optional)
   - Configure SSL certificate
   - Set up Application Insights

### Phase 6: Testing & Cutover (Week 3-4)

1. **Comprehensive Testing**
   - Test all features
   - Load testing
   - Security testing
   - User acceptance testing

2. **Cutover Plan**
   - Schedule maintenance window
   - Final data sync
   - DNS cutover (if using custom domain)
   - Monitor for issues

3. **Post-Migration**
   - Monitor application health
   - Set up alerts
   - Document new processes
   - Train users on new access method

## Security Considerations

### Database Security
- ✅ **Encryption at Rest**: Automatic with Azure Database for PostgreSQL
- ✅ **Encryption in Transit**: TLS enforced
- ✅ **Firewall Rules**: IP whitelisting
- ✅ **Azure AD Authentication**: Use Entra ID for database access
- ✅ **Automated Backups**: 7-35 days retention
- ✅ **Point-in-Time Restore**: Available

### Application Security
- ✅ **HTTPS Only**: Enforced by Azure App Service
- ✅ **Managed SSL Certificates**: Free with App Service
- ✅ **Network Isolation**: VNet integration available
- ✅ **Secrets Management**: Azure Key Vault integration
- ✅ **Managed Identity**: Prefer Managed Identity + `DefaultAzureCredential` to avoid secrets
- ✅ **Application Insights**: Security monitoring

### Storage Security
- ✅ **Private Containers**: Default configuration
- ✅ **Encryption at Rest**: Automatic
- ✅ **Access Control**: Azure AD integration
- ✅ **SAS Tokens**: For temporary access
- ✅ **Versioning**: Available for blob storage

### Authentication Security
- ✅ **Single Sign-On**: With Office 365
- ✅ **Multi-Factor Authentication**: Supported
- ✅ **Conditional Access**: Policies available
- ✅ **Token-Based**: Secure JWT tokens
- ✅ **Session Management**: Built-in

## Cost Estimation

### Monthly Costs (Approximate)

**Revised Tiering Suggestions**

| Service | Suggested Tier | Reason |
| --- | --- | --- |
| App Service | B1 (Linux) | Cheapest tier that supports Always On and custom domains |
| Database | PostgreSQL Flexible (Burstable B1ms) | Good for 5–10 users and supports cost-saving auto-stop |
| Storage | LRS (Locally Redundant) | Sufficient for lab use and lower cost |

**Azure Database for PostgreSQL (Flexible Server - Burstable B1ms)**
- ~$15/month for small workloads
- Supports auto-stop for cost savings

**Azure App Service (Basic B1)**
- ~$13/month for 1.75GB RAM, 1 CPU
- Supports **Always On** and custom domains

**Azure Blob Storage (LRS)**
- ~$0.0184/GB/month for first 50TB
- Transaction costs: ~$0.004 per 10,000 transactions

**Azure Active Directory**
- Free tier includes basic features
- Premium features: ~$6/user/month (if needed)

**Total Estimated Monthly Cost: ~$30-50/month**

*Note: Costs vary by region, usage, and tier selection. Use Azure Pricing Calculator for accurate estimates.*

## Required Code Changes

### 1. Update `config/storage.py`

Add Azure configuration support (if not already complete):

```python
# Add to get_storage_config() function
elif STORAGE_TYPE == "azure":
    return {
        "type": "azure",
        "connection_string": os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        "container": os.getenv("AZURE_STORAGE_CONTAINER", "uploads"),
        "backup_directory": BACKUP_DIRECTORY
    }
```

### 2. Create `auth/azure_ad.py`

New authentication module for Azure AD:

```python
from msal import ConfidentialClientApplication
import os
from dotenv import load_dotenv

load_dotenv()

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"

def get_azure_ad_app():
    """Initialize Azure AD application."""
    return ConfidentialClientApplication(
        client_id=AZURE_CLIENT_ID,
        client_credential=AZURE_CLIENT_SECRET,
        authority=AZURE_AUTHORITY
    )

def verify_azure_token(token):
    """Verify Azure AD token."""
    app = get_azure_ad_app()
    result = app.acquire_token_by_authorization_code(
        code=token,
        scopes=["User.Read"]
    )
    return result
```

**Shortcut for Streamlit**: Consider `streamlit-msal` or `streamlit-microsoft-auth` to handle OAuth redirects cleanly within Streamlit's rerun lifecycle.

### 3. Update `config/config.py`

Ensure database URL validation supports PostgreSQL:

```python
# Already supports 'mssql' and 'postgresql' - no changes needed!
```

### 4. Create `startup.sh` for Azure App Service

```bash
#!/bin/bash
streamlit run app.py --server.port=8000 --server.address=0.0.0.0 --server.enableCORS=false
```

### 5. Create `.deployment` file

```
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

## Environment Variables for Azure

Create `.env` file or configure in Azure Portal:

```bash
# Database
DATABASE_URL=postgresql://user:password@server.postgres.database.azure.com:5432/experiments

# Storage
STORAGE_TYPE=azure
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER=uploads
BACKUP_DIRECTORY=/home/backups

# Authentication
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id

# App Configuration
APP_NAME=Addis Energy Research
```

*Note: If using Managed Identity with `DefaultAzureCredential`, you can omit storage connection strings and use account URLs instead.*

## Migration Checklist

### Pre-Migration
- [ ] Create Azure account and subscription
- [ ] Set up billing alerts
- [ ] Create resource group
- [ ] Backup current database
- [ ] Export all uploaded files
- [ ] Document current configuration

### Database Migration
- [ ] Create Azure Database for PostgreSQL (Flexible Server)
- [ ] Configure firewall rules
- [ ] Migrate data with SQLAlchemy/pandas or `pgloader`
- [ ] Run Alembic migrations
- [ ] Test database connection
- [ ] Verify data integrity

### Storage Migration
- [ ] Create Azure Storage Account
- [ ] Create blob container
- [ ] Update storage configuration
- [ ] Migrate existing files
- [ ] Update database file paths
- [ ] Test file operations

### Authentication Migration
- [ ] Register app in Azure AD
- [ ] Configure redirect URIs
- [ ] Create Azure AD auth module
- [ ] Update authentication components
- [ ] Test login flow
- [ ] Migrate users (if needed)

### Application Deployment
- [ ] Create Azure App Service
- [ ] Configure deployment
- [ ] Set environment variables
- [ ] Deploy application
- [ ] Enable ARR Affinity (Session Affinity)
- [ ] Enable Always On
- [ ] Configure custom domain (optional)
- [ ] Set up monitoring

### Post-Migration
- [ ] Comprehensive testing
- [ ] User acceptance testing
- [ ] Performance monitoring
- [ ] Security audit
- [ ] Documentation update
- [ ] User training

## Troubleshooting Common Issues

### Database Connection Issues
- **Problem**: Cannot connect to Azure Database for PostgreSQL
- **Solution**: Check firewall rules, verify connection string, ensure Azure AD authentication is configured

### File Upload Issues
- **Problem**: Files not uploading to Azure Blob Storage
- **Solution**: Verify connection string, check container permissions, ensure storage account is accessible

### Authentication Issues
- **Problem**: Users cannot log in with Azure AD
- **Solution**: Verify app registration, check redirect URIs, ensure client ID/secret are correct

### Deployment Issues
- **Problem**: App not starting in Azure App Service
- **Solution**: Check startup command, verify Python version, review application logs

## Alternative Options

If Azure doesn't meet your needs, consider:

1. **AWS (Amazon Web Services)**
   - Similar services (RDS, S3, App Runner)
   - More complex setup
   - Your code already supports S3

2. **Google Cloud Platform**
   - Similar services (Cloud SQL, Cloud Storage, Cloud Run)
   - Your code already supports GCS
   - Good for Firebase migration

3. **Heroku**
   - Simpler deployment
   - More expensive at scale
   - Limited customization

4. **DigitalOcean App Platform**
   - Simpler than AWS/Azure
   - Good for small-medium apps
   - Less enterprise features

## Getting Help

### Azure Resources
- [Azure Documentation](https://docs.microsoft.com/azure/)
- [Azure Database for PostgreSQL Docs](https://docs.microsoft.com/azure/postgresql/)
- [Azure App Service Docs](https://docs.microsoft.com/azure/app-service/)
- [Azure AD Authentication](https://docs.microsoft.com/azure/active-directory/)

### Community Support
- [Azure Community Forums](https://techcommunity.microsoft.com/t5/azure/ct-p/Azure)
- [Stack Overflow - Azure Tag](https://stackoverflow.com/questions/tagged/azure)
- [Reddit r/AZURE](https://www.reddit.com/r/AZURE/)

## Next Steps

1. **Review this guide** with your team
2. **Set up Azure account** and create resources
3. **Start with database migration** and test local app → Azure DB connectivity
4. **Test in staging environment** before production
5. **Plan maintenance window** for cutover
6. **Monitor closely** after migration

## Conclusion

Azure is an excellent choice for your migration. The transition is **moderately complex** but very manageable, especially since:
- ✅ Azure Blob Storage support already exists
- ✅ SQLAlchemy makes database switching easy
- ✅ Streamlit deployment is straightforward
- ✅ Microsoft integration aligns with your existing infrastructure

**Estimated Timeline:** 3-4 weeks for a beginner
**Estimated Cost:** ~$30-50/month
**Risk Level:** Low-Medium (with proper planning)

The security benefits, reliability, and integration with your Microsoft environment make this migration highly worthwhile.
