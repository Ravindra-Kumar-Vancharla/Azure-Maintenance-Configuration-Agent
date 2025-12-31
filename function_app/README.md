# Azure Functions - Maintenance Configuration API

Azure Functions v2 Python Programming Model for retrieving Azure Maintenance Configuration details.

## Features

- ✅ Azure Functions v2 Programming Model
- ✅ HTTP Trigger endpoints
- ✅ Managed Identity authentication
- ✅ RESTful API design
- ✅ Health check endpoint
- ✅ Identity diagnostic endpoint

## Prerequisites

- Python 3.9+
- Azure Functions Core Tools v4.x
- Azure CLI (authenticated with `az login`)
- Azure subscription with maintenance configurations

## Project Structure

```
function_app/
├── function_app.py          # Main function app with HTTP triggers
├── requirements.txt         # Python dependencies
├── host.json               # Function app configuration
├── local.settings.json     # Local environment variables
└── README.md              # This file
```

## Local Development

### 1. Install Dependencies

```bash
cd function_app
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Azure Functions Core Tools

```bash
# macOS
brew tap azure/functions
brew install azure-functions-core-tools@4

# Windows
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

### 3. Configure Local Settings

Edit `local.settings.json` and set your Azure subscription:

```json
{
  "Values": {
    "AZURE_SUBSCRIPTION_ID": "your-subscription-id",
    "AZURE_RESOURCE_GROUP": "your-resource-group"
  }
}
```

### 4. Run Locally

```bash
func start
```

The function app will start at `http://localhost:7071`

## API Endpoints

### 1. Get Maintenance Configurations

**Endpoint:** `GET /api/maintenance-configs`

**Query Parameters:**
- `subscription_id` (required) - Azure subscription ID
- `resource_group` (optional) - Filter by resource group
- `configuration_name` (optional) - Get specific configuration

**Examples:**

```bash
# Get all configurations in subscription
curl "http://localhost:7071/api/maintenance-configs?subscription_id=343c17eb-34b6-4481-92a2-a0a5a04bdd88"

# Filter by resource group
curl "http://localhost:7071/api/maintenance-configs?subscription_id=343c17eb-34b6-4481-92a2-a0a5a04bdd88&resource_group=rg-cp-ravindra-vancharla"

# Get specific configuration
curl "http://localhost:7071/api/maintenance-configs?subscription_id=343c17eb-34b6-4481-92a2-a0a5a04bdd88&resource_group=rg-cp-ravindra-vancharla&configuration_name=mc-chg0034567-orders"
```

**Response:**

```json
{
  "subscription_id": "343c17eb-34b6-4481-92a2-a0a5a04bdd88",
  "configurations": [
    {
      "name": "mc-chg0034567-orders",
      "resource_group": "rg-cp-ravindra-vancharla",
      "location": "eastus",
      "maintenance_scope": "InGuestPatch",
      "visibility": "Custom",
      "start_date_time": "2025-11-28 14:50:00+00:00",
      "duration": "01:30:00",
      "time_zone": "UTC",
      "recur_every": "1Week"
    }
  ],
  "total_configurations": 1
}
```

### 2. Health Check

**Endpoint:** `GET /api/health`

**Example:**

```bash
curl http://localhost:7071/api/health
```

**Response:**

```json
{
  "status": "healthy",
  "service": "maintenance-configuration-api"
}
```

### 3. Identity Information

**Endpoint:** `GET /api/identity`

Useful for debugging authentication issues.

**Example:**

```bash
curl http://localhost:7071/api/identity
```

**Response:**

```json
{
  "success": true,
  "identity_type": "user",
  "object_id": "your-object-id",
  "app_id": "your-app-id",
  "tenant_id": "your-tenant-id"
}
```

## Deploy to Azure

### 1. Create Azure Function App

```bash
# Set variables
RESOURCE_GROUP="rg-cp-ravindra-vancharla"
FUNCTION_APP_NAME="maintenance-config-api"  # Must be globally unique
LOCATION="eastus"
STORAGE_ACCOUNT="maintstorage$(date +%s)"  # Unique name

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# Create Function App with managed identity
az functionapp create \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --storage-account $STORAGE_ACCOUNT \
  --os-type Linux \
  --assign-identity [system]
```

### 2. Grant Permissions to Managed Identity

```bash
# Get the Function App's managed identity
IDENTITY_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Grant Reader role
SUBSCRIPTION_ID="343c17eb-34b6-4481-92a2-a0a5a04bdd88"

az role assignment create \
  --assignee $IDENTITY_ID \
  --role "Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
```

### 3. Deploy Function Code

```bash
# From the function_app directory
func azure functionapp publish $FUNCTION_APP_NAME
```

### 4. Configure Application Settings

```bash
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_SUBSCRIPTION_ID="343c17eb-34b6-4481-92a2-a0a5a04bdd88" \
    AZURE_RESOURCE_GROUP="rg-cp-ravindra-vancharla"
```

### 5. Test Deployed Function

```bash
# Get function key
FUNCTION_KEY=$(az functionapp keys list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query functionKeys.default -o tsv)

# Test the endpoint
curl "https://$FUNCTION_APP_NAME.azurewebsites.net/api/maintenance-configs?code=$FUNCTION_KEY&subscription_id=343c17eb-34b6-4481-92a2-a0a5a04bdd88&resource_group=rg-cp-ravindra-vancharla"
```

## Authentication

### Local Development
Uses `DefaultAzureCredential` which tries:
1. Environment variables
2. Managed Identity (when running in Azure)
3. Azure CLI credentials (`az login`)

### Production (Azure)
Uses System-assigned Managed Identity automatically.

## Troubleshooting

### Permission Errors (403)
The Function App's managed identity needs Reader role:

```bash
az role assignment create \
  --assignee <managed-identity-id> \
  --role "Reader" \
  --scope "/subscriptions/<subscription-id>"
```

### Local Development Issues
1. Ensure you're logged in: `az login`
2. Check `local.settings.json` has correct values
3. Verify Python version: `python --version` (3.9+)

### Function Not Found (404)
1. Check the function is deployed: `func azure functionapp list-functions $FUNCTION_APP_NAME`
2. Verify the route in function_app.py matches your URL

## Security Best Practices

1. **Use Managed Identity** - No credentials in code
2. **Function-level auth** - Require function keys for production
3. **CORS Configuration** - Restrict allowed origins
4. **Input Validation** - Validate all query parameters
5. **Least Privilege** - Grant only Reader role, not Contributor

## Monitoring

View logs in Azure:

```bash
# Stream logs
func azure functionapp logstream $FUNCTION_APP_NAME

# Or in Azure Portal
# Go to Function App → Monitor → Live Metrics
```

## Cost Optimization

- Uses **Consumption Plan** - pay only for execution time
- Estimated cost: ~$0.20 per 1M requests
- First 1M requests/month are free

## Next Steps

1. Add Application Insights for detailed telemetry
2. Implement caching for frequently accessed configs
3. Add OpenAPI/Swagger documentation
4. Set up CI/CD pipeline with GitHub Actions
5. Add authentication with Azure AD

## Support

For issues or questions:
- Check Azure Functions documentation: https://learn.microsoft.com/azure/azure-functions/
- Review maintenance configurations: https://learn.microsoft.com/azure/maintenance-configurations/
