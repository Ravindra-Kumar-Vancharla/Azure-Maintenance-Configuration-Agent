from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest

credential = DefaultAzureCredential()
subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
vm_name = "patchubuntuserver"

arg_client = ResourceGraphClient(credential)

# First, let's see what PatchInstallationResources records exist
query = f"""
PatchInstallationResources
| where type =~ "microsoft.compute/virtualmachines/patchinstallationresults"
| where tolower(name) contains '{vm_name.lower()}'
| project 
    id,
    name,
    rebootStatus = tostring(properties.rebootStatus),
    lastModified = tostring(properties.lastModifiedDateTime),
    status = tostring(properties.status)
| order by lastModified desc
| take 3
"""

print("Testing query for patchubuntuserver...")
print(f"Query: {query}\n")

try:
    request = QueryRequest(subscriptions=[subscription_id], query=query)
    response = arg_client.resources(request)
    
    print(f"Total count: {response.total_records}")
    print(f"Data rows: {len(response.data)}\n")
    
    if response.data:
        for i, row in enumerate(response.data):
            print(f"Row {i+1}:")
            print(f"  ID: {row.get('id')}")
            print(f"  Name: {row.get('name')}")
            print(f"  Status: {row.get('status')}")
            print(f"  Reboot Status: {row.get('rebootStatus')}")
            print(f"  Last Modified: {row.get('lastModified')}")
            print()
    else:
        print("No data returned")
        
except Exception as e:
    print(f"Error: {e}")
