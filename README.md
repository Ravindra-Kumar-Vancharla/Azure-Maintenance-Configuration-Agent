# Azure Maintenance Configuration Agent

An AI Foundry agent that provides information about Azure Maintenance Configurations and associated Virtual Machines.

## Features

- **List Maintenance Configurations**: Get all maintenance configurations in a subscription or resource group
- **Get Configuration Details**: View detailed information about specific maintenance configurations including:
  - Schedule (start time, recurrence, duration)
  - Time zone
  - Maintenance scope
  - Assigned resources
- **List VMs in Configuration**: Find all VMs assigned to a specific maintenance configuration

## Prerequisites

1. **Azure Account** with appropriate permissions:
   - Reader access to subscriptions/resource groups
   - Access to view maintenance configurations
   - Access to view virtual machines

2. **Azure AI Foundry Project** with:
   - A created agent (get the Agent ID)
   - Project endpoint URL
   - Appropriate model deployment (e.g., gpt-4)

3. **Python 3.8+**

4. **Azure CLI** (for authentication):
   ```bash
   az login
   ```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or update `.env` file:

```bash
# Azure AI Foundry
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project
MODEL_DEPLOYMENT_NAME=gpt-4.1
AGENT_ID=asst_xxxxxxxxxxxxx

# Azure Subscription
AZURE_SUBSCRIPTION_ID=your-subscription-id-here

# Optional
VECTOR_STORE_ID=vs_xxxxxxxxxxxxx  # If using file search
```

### 3. Authenticate with Azure

```bash
az login
```

## Usage

### Interactive Mode

Run the agent interactively:

```bash
python main.py
```

Then enter your query when prompted.

### Command Line Mode

Pass your query as an argument:

```bash
python main.py "List all maintenance configurations in my subscription"
```

### Example Queries

```bash
# List all maintenance configurations
python main.py "Show me all maintenance configurations"

# Get specific configuration details
python main.py "Get details of maintenance configuration 'weekly-patch' in resource group 'prod-rg'"

# List VMs in a configuration
python main.py "Which VMs are assigned to maintenance configuration 'monthly-update' in resource group 'production'?"

# Get schedule information
python main.py "What is the schedule for maintenance configuration 'weekend-maintenance'?"
```

### Test Mode (Direct Function Calls)

Test the functions without the agent:

```bash
python main.py --test
```

Or use the test script:

```bash
python test_maintenance_functions.py direct
```

## Available Functions

### 1. `get_maintenance_configuration_details()`

Get maintenance configuration details and assigned resources.

**Parameters:**
- `subscription_id` (required): Azure subscription ID
- `resource_group` (optional): Resource group name
- `configuration_name` (optional): Specific configuration name

**Returns:**
```json
{
  "subscription_id": "xxx",
  "configurations": [
    {
      "name": "weekly-patch",
      "location": "eastus",
      "maintenance_scope": "InGuestPatch",
      "start_date_time": "2025-01-01 02:00:00",
      "duration": "02:00:00",
      "time_zone": "Pacific Standard Time",
      "recur_every": "Week Monday",
      "assigned_resources": [...]
    }
  ],
  "total_configurations": 1
}
```

### 2. `list_vms_in_maintenance_configuration()`

List all VMs assigned to a specific maintenance configuration.

**Parameters:**
- `subscription_id` (required): Azure subscription ID
- `resource_group` (required): Resource group containing the configuration
- `configuration_name` (required): Name of the maintenance configuration

**Returns:**
```json
{
  "subscription_id": "xxx",
  "maintenance_configuration": {
    "name": "weekly-patch",
    "resource_group": "prod-rg",
    "maintenance_scope": "InGuestPatch"
  },
  "assigned_vms": [
    {
      "vm_name": "prod-vm-01",
      "resource_group": "prod-rg",
      "location": "eastus",
      "vm_size": "Standard_D4s_v3",
      "provisioning_state": "Succeeded"
    }
  ],
  "total_vms": 1
}
```

## Project Structure

```
functionagentfetchvmstatus/
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
├── main.py                       # Main entry point
├── test_maintenance_functions.py # Test script
└── vmstatusagent/
    ├── agent.py                  # Agent runner logic
    ├── agentcreate.py           # Agent creation/configuration
    └── user_functions.py        # Function implementations
```

## Troubleshooting

### Authentication Issues

If you get authentication errors:

```bash
# Re-authenticate with Azure
az login

# Verify your login
az account show

# Set default subscription if needed
az account set --subscription "your-subscription-id"
```

### Missing Environment Variables

Ensure all required variables are set in `.env`:
- `PROJECT_ENDPOINT`
- `AGENT_ID`
- `AZURE_SUBSCRIPTION_ID`

### Permission Errors

Ensure your Azure account has:
- Reader role on the subscription/resource group
- Permission to view maintenance configurations
- Permission to view virtual machines

### Function Not Found

If the agent can't find functions:
1. Check that functions are added to `user_functions` dictionary in `user_functions.py`
2. Verify the agent was updated with the new toolset
3. Try recreating the agent

## Development

### Adding New Functions

1. Define your function in `vmstatusagent/user_functions.py`:

```python
def my_new_function(subscription_id: str, param1: str) -> Dict[str, Any]:
    """Function description"""
    # Implementation
    return {"result": "data"}
```

2. Add it to the `user_functions` dictionary:

```python
user_functions = {
    "my_new_function": my_new_function,
    # ... other functions
}
```

3. Update agent instructions in `agentcreate.py` if needed

4. Test your function:

```python
from vmstatusagent.user_functions import my_new_function
result = my_new_function("subscription-id", "param-value")
print(result)
```

## Azure API References

- [Maintenance Configurations](https://learn.microsoft.com/en-us/rest/api/maintenance/maintenance-configurations)
- [Configuration Assignments](https://learn.microsoft.com/en-us/rest/api/maintenance/configuration-assignments)
- [Virtual Machines](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines)

## License

MIT
