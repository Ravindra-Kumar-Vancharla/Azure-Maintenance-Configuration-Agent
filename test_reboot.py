from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest

credential = DefaultAzureCredential()
subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
vm_name = "patchubuntuserver"

arg_client = ResourceGraphClient(credential)

query = f"""
PatchInstallationResources
| where type =~ "microsoft.compute/virtualmachines/patchinstallationresults"
| parse tolower(id) with resourceId "/patchinstallationresults" *
| where resourceId contains '{vm_name.lower()}'
| project 
    rebootStatus = tostring(properties.rebootStatus),
    lastModified = todatetime(properties.lastModifiedDateTime),
    startTime = todatetime(properties.startDateTime)
| order by lastModified desc
| take 1
"""

print("Query:")
print(query)
print("\nResults:")

request = QueryRequest(subscriptions=[subscription_id], query=query)
response = arg_client.resources(request)

for row in response.data:
    print(f"  Reboot Status: {row.get('rebootStatus')}")
    print(f"  Last Modified: {row.get('lastModified')}")
    print(f"  Start Time: {row.get('startTime')}")
