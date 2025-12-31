from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest

credential = DefaultAzureCredential()
subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
resource_group = "rg-cp-ravindra-vancharla"
vm_name = "patchubuntuserver"

# First get the full resource ID
compute_client = ComputeManagementClient(credential, subscription_id)
vm = compute_client.virtual_machines.get(resource_group, vm_name)
vm_resource_id = vm.id

print(f"VM Resource ID: {vm_resource_id}\n")

# Now query ARG using the resource ID
arg_client = ResourceGraphClient(credential)

query = f"""
PatchInstallationResources
| where type =~ "microsoft.compute/virtualmachines/patchinstallationresults"
| parse tolower(id) with resourceId "/patchinstallationresults" *
| where resourceId =~ '{vm_resource_id.lower()}'
| project 
    rebootStatus = tostring(properties.rebootStatus),
    status = tostring(properties.status),
    lastModified = tostring(properties.lastModifiedDateTime)
| order by lastModified desc
| take 1
"""

print("ARG Query:")
print(query)
print()

try:
    request = QueryRequest(subscriptions=[subscription_id], query=query)
    response = arg_client.resources(request)
    
    print(f"Total records: {response.total_records}")
    if response.data:
        for row in response.data:
            print(f"  Reboot Status: {row.get('rebootStatus')}")
            print(f"  Status: {row.get('status')}")
            print(f"  Last Modified: {row.get('lastModified')}")
    else:
        print("No data returned")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
