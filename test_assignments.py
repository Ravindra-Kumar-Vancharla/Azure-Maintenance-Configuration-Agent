from azure.identity import DefaultAzureCredential
from azure.mgmt.maintenance import MaintenanceManagementClient

credential = DefaultAzureCredential()
subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
client = MaintenanceManagementClient(credential, subscription_id)

print("=== Checking Configuration Assignments ===\n")

# Try different methods to list assignments
try:
    print("1. Trying list_subscription()...")
    assignments = client.configuration_assignments.list_subscription()
    count = 0
    for assignment in assignments:
        count += 1
        print(f"\nAssignment {count}:")
        print(f"  ID: {assignment.id}")
        print(f"  Name: {assignment.name}")
        print(f"  Maintenance Config ID: {assignment.maintenance_configuration_id}")
    print(f"\nTotal assignments found: {count}")
except Exception as e:
    print(f"Error: {e}")

# Try listing by resource group
print("\n\n2. Trying list by resource group...")
try:
    vms = ["testwindows", "ubuntuserver1", "ubuntutestserver", "windowstest", "patchubuntuserver"]
    for vm_name in vms:
        try:
            assignments = client.configuration_assignments.list(
                resource_group_name="rg-cp-ravindra-vancharla",
                provider_name="Microsoft.Compute",
                resource_type="virtualMachines",
                resource_name=vm_name
            )
            for assignment in assignments:
                print(f"\nVM: {vm_name}")
                print(f"  Assignment: {assignment.name}")
                print(f"  Config: {assignment.maintenance_configuration_id}")
        except Exception as e:
            print(f"VM {vm_name}: {e}")
except Exception as e:
    print(f"Error: {e}")
