from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

credential = DefaultAzureCredential()
subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
client = ComputeManagementClient(credential, subscription_id)

vm_name = "patchubuntuserver"
rg_name = "rg-cp-ravindra-vancharla"

print(f"=== Checking {vm_name} ===\n")

# Get VM with instance view
vm = client.virtual_machines.get(
    resource_group_name=rg_name,
    vm_name=vm_name,
    expand="instanceView"
)

print(f"VM Name: {vm.name}")
print(f"Location: {vm.location}")
print(f"OS Type: {vm.storage_profile.os_disk.os_type}")

if vm.instance_view:
    print(f"\nPower State:")
    for status in vm.instance_view.statuses:
        if 'PowerState' in status.code:
            print(f"  {status.display_status}")
    
    print(f"\nVM Agent Status:")
    if hasattr(vm.instance_view, 'vm_agent') and vm.instance_view.vm_agent:
        print(f"  Status: {vm.instance_view.vm_agent.vm_agent_version}")
        print(f"  Statuses: {vm.instance_view.vm_agent.statuses}")
    else:
        print("  No VM Agent information available")
    
    print(f"\nPatch Status:")
    if hasattr(vm.instance_view, 'patch_status'):
        patch_status = vm.instance_view.patch_status
        print(f"  Patch Status Object Exists: Yes")
        print(f"  Attributes: {dir(patch_status)}")
        
        if hasattr(patch_status, 'available_patch_summary'):
            summary = patch_status.available_patch_summary
            print(f"\n  Available Patch Summary:")
            print(f"    - Object: {summary}")
            if summary:
                print(f"    - Critical/Security: {getattr(summary, 'critical_and_security_patch_count', 'N/A')}")
                print(f"    - Other: {getattr(summary, 'other_patch_count', 'N/A')}")
                print(f"    - Assessment Time: {getattr(summary, 'assessment_activity_id', 'N/A')}")
        else:
            print(f"  No available_patch_summary attribute")
            
        if hasattr(patch_status, 'last_patch_installation_summary'):
            last_install = patch_status.last_patch_installation_summary
            print(f"\n  Last Installation Summary:")
            print(f"    - Object: {last_install}")
            if last_install:
                print(f"    - Status: {getattr(last_install, 'status', 'N/A')}")
                print(f"    - Installed: {getattr(last_install, 'installed_patch_count', 'N/A')}")
                print(f"    - Failed: {getattr(last_install, 'failed_patch_count', 'N/A')}")
    else:
        print("  No patch_status attribute found on instance_view")
        print(f"  Available attributes on instance_view: {[attr for attr in dir(vm.instance_view) if not attr.startswith('_')]}")
else:
    print("No instance view available")

print("\n=== Checking if VM has Azure extensions ===")
extensions = client.virtual_machine_extensions.list(
    resource_group_name=rg_name,
    vm_name=vm_name
)
for ext in extensions:
    print(f"  - {ext.name}: {ext.type_properties_type} (Publisher: {ext.publisher})")
