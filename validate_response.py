from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.maintenance import MaintenanceManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
import json

credential = DefaultAzureCredential()
subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
rg = "rg-cp-ravindra-vancharla"
vm_name = "patchubuntuserver"

print("=" * 80)
print("VALIDATION: Checking patchubuntuserver data")
print("=" * 80)

# 1. Check maintenance configuration
print("\n1. MAINTENANCE CONFIGURATION: patchschedule1")
maintenance_client = MaintenanceManagementClient(credential, subscription_id)
config = maintenance_client.maintenance_configurations.get(rg, "patchschedule1")
print(f"   ✓ Location: {config.location}")
print(f"   ✓ Scope: {config.maintenance_scope}")
print(f"   ✓ Start: {config.start_date_time} ({config.time_zone})")
print(f"   ✓ Duration: {config.duration}")
print(f"   ✓ Recurrence: {config.recur_every}")

# 2. Check VM current state
print(f"\n2. VM CURRENT STATE: {vm_name}")
compute_client = ComputeManagementClient(credential, subscription_id)
vm = compute_client.virtual_machines.get(rg, vm_name, expand="instanceView")

power_state = next((s.display_status for s in vm.instance_view.statuses if 'PowerState' in s.code), "Unknown")
print(f"   ✓ Power State: {power_state}")

if hasattr(vm.instance_view, 'patch_status') and vm.instance_view.patch_status:
    patch_status = vm.instance_view.patch_status
    if patch_status.available_patch_summary:
        aps = patch_status.available_patch_summary
        print(f"   ✓ Assessment Status: {aps.status}")
        print(f"   ✓ Assessment ID: {aps.assessment_activity_id}")
        print(f"   ✓ Critical/Security: {aps.critical_and_security_patch_count}")
        print(f"   ✓ Other Patches: {aps.other_patch_count}")
        print(f"   ✓ Reboot Pending: {aps.reboot_pending}")

# 3. Check patch installation history
print(f"\n3. PATCH INSTALLATION HISTORY (Last 30 days)")
arg_client = ResourceGraphClient(credential)

query = f"""
PatchInstallationResources
| where properties.lastModifiedDateTime > ago(30d)
| where type =~ "microsoft.compute/virtualmachines/patchinstallationresults"
| parse tolower(id) with resourceId "/patchinstallationresults" *
| where resourceId contains '{vm_name.lower()}'
| project 
    status = tostring(properties.status),
    startTime = todatetime(properties.startDateTime),
    lastModified = todatetime(properties.lastModifiedDateTime),
    installed = toint(properties.installedPatchCount),
    failed = toint(properties.failedPatchCount),
    pending = toint(properties.pendingPatchCount),
    rebootStatus = tostring(properties.rebootStatus),
    startedBy = tostring(properties.startedBy)
| order by lastModified desc
| take 1
"""

request = QueryRequest(subscriptions=[subscription_id], query=query)
response = arg_client.resources(request)

if response.data:
    last_run = response.data[0]
    print(f"   ✓ Status: {last_run.get('status')}")
    print(f"   ✓ Start Time: {last_run.get('startTime')}")
    print(f"   ✓ Installed: {last_run.get('installed')}")
    print(f"   ✓ Failed: {last_run.get('failed')}")
    print(f"   ✓ Pending: {last_run.get('pending')}")
    print(f"   ✓ Reboot Status: {last_run.get('rebootStatus')}")
    print(f"   ✓ Started By: {last_run.get('startedBy')}")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
