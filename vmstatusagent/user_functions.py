# agent/user_functions.py
"""
Generic FunctionTool user functions template.
 
Use this file to:
- Define agent-callable functions
- Keep them deterministic & read-only
- Return compact JSON-serializable dicts
"""
 
import logging
from typing import Dict, Any, Optional
 
from azure.identity import DefaultAzureCredential
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# ------------------------------------------------
# Shared credential (cached)
# ------------------------------------------------
_credential: Optional[DefaultAzureCredential] = None
 
def get_credential() -> DefaultAzureCredential:
    """
    Lazily create and cache Azure credential.
    """
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential
 
 
# ------------------------------------------------
# GENERIC FUNCTION TEMPLATE
# ------------------------------------------------
def example_diagnostic_function(
    subscription_id: str,
    resource_group: str,
    resource_name: str,
    issue_type: str,
    **kwargs
) -> Dict[str, Any]:
    """
    TEMPLATE FUNCTION
 
    Rules:
    - Must be deterministic
    - Must NOT modify Azure resources
    - Must return JSON-serializable dict
    - Keep output compact
 
    Parameters are flexible — add/remove as needed.
    """
 
    logger.info(
        "Running example diagnostic: sub=%s rg=%s resource=%s issue=%s",
        subscription_id, resource_group, resource_name, issue_type
    )
 
    try:
        # TODO: add real diagnostic logic here
        # Example: query Azure resource, read metrics, inspect config
 
        return {
            "resource_name": resource_name,
            "resource_group": resource_group,
            "issue_type": issue_type,
            "status": "ok",
            "details": "Replace this with real diagnostics",
        }
 
    except Exception as e:
        logger.exception("Diagnostic function failed")
        return {
            "resource_name": resource_name,
            "resource_group": resource_group,
            "issue_type": issue_type,
            "error": str(e),
        }
 
 
# ------------------------------------------------
# ADD NEW FUNCTIONS BELOW
# ------------------------------------------------
def get_maintenance_configuration_details(
    subscription_id: str,
    resource_group: str = None,
    configuration_name: str = None
) -> Dict[str, Any]:
    """
    Get maintenance configuration details.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: (Optional) Resource group name - if not provided, lists all in subscription
        configuration_name: (Optional) Specific configuration name - if not provided, lists all
    
    Returns:
        Dict with maintenance configuration details
    """
    from azure.mgmt.maintenance import MaintenanceManagementClient
    from azure.core.exceptions import ResourceNotFoundError
    
    logger.info(
        "Getting maintenance configuration: sub=%s rg=%s config=%s",
        subscription_id, resource_group, configuration_name
    )
    
    try:
        credential = get_credential()
        client = MaintenanceManagementClient(credential, subscription_id)
        
        configurations = []
        all_configs = []  # Initialize to avoid UnboundLocalError
        
        # Get specific configuration or list all
        if configuration_name and resource_group:
            try:
                config = client.maintenance_configurations.get(
                    resource_group_name=resource_group,
                    resource_name=configuration_name
                )
                configurations = [config]
                all_configs = [config]  # Set for debug info
            except ResourceNotFoundError:
                return {
                    "error": f"Configuration '{configuration_name}' not found in resource group '{resource_group}'"
                }
        else:
            # List all in subscription, then filter by resource group if specified
            configs = client.maintenance_configurations.list()
            all_configs = list(configs)
            
            logger.info("Found %d total configurations in subscription", len(all_configs))
            
            if resource_group:
                # Filter by resource group - match exact resource group name in ID
                # ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Maintenance/maintenanceConfigurations/{name}
                configurations = []
                for c in all_configs:
                    rg_from_id = c.id.split('/')[4] if len(c.id.split('/')) > 4 else ""
                    logger.info("Config '%s' has resource_group='%s', looking for '%s'", c.name, rg_from_id, resource_group)
                    if rg_from_id.lower() == resource_group.lower():
                        configurations.append(c)
                
                logger.info("After filtering by resource_group '%s': %d configurations", resource_group, len(configurations))
            else:
                configurations = all_configs
        
        result = {
            "subscription_id": subscription_id,
            "configurations": [],
            "debug_info": {
                "total_in_subscription": len(all_configs),
                "requested_resource_group": resource_group,
                "configs_after_filter": len(configurations)
            }
        }
        
        # Process each configuration
        for config in configurations:
            config_data = {
                "name": config.name,
                "id": config.id,
                "location": config.location,
                "resource_group": config.id.split('/')[4],
                "maintenance_scope": config.maintenance_scope,
                "visibility": getattr(config, 'visibility', None),
                "start_date_time": getattr(config, 'start_date_time', None),
                "expiration_date_time": getattr(config, 'expiration_date_time', None),
                "duration": getattr(config, 'duration', None),
                "time_zone": getattr(config, 'time_zone', None),
                "recur_every": getattr(config, 'recur_every', None),
            }
            
            result["configurations"].append(config_data)
        
        result["total_configurations"] = len(configurations)
        return result
        
    except Exception as e:
        logger.exception("Failed to get maintenance configuration details")
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Add helpful context for common errors
        troubleshooting = ""
        if "AuthenticationError" in error_type or "unauthorized" in error_msg.lower():
            troubleshooting = "Authentication failed. The agent's managed identity needs Reader role on the subscription or resource group."
        elif "Forbidden" in error_msg or "403" in error_msg:
            troubleshooting = "Permission denied. Grant the agent's managed identity Reader role: az role assignment create --assignee <identity-id> --role Reader --scope /subscriptions/343c17eb-34b6-4481-92a2-a0a5a04bdd88"
        elif "ResourceNotFound" in error_type or "404" in error_msg:
            troubleshooting = "Resource not found. Verify the subscription ID and resource group name are correct."
        
        return {
            "subscription_id": subscription_id,
            "error": error_msg,
            "error_type": error_type,
            "troubleshooting": troubleshooting,
            "note": "This error occurred when trying to access Azure Maintenance Configurations. Check permissions and authentication."
        }


def get_patch_installation_history(
    subscription_id: str,
    days: int = 30,
    resource_group: str = None
) -> Dict[str, Any]:
    """
    Get patch installation history from Azure Update Manager using Azure Resource Graph.
    This shows actual patch installation runs from the last N days.
    
    Args:
        subscription_id: Azure subscription ID
        days: Number of days of history to retrieve (default 30)
        resource_group: Optional resource group to filter results
        
    Returns:
        Dict with patch installation history and statistics
    """
    from azure.mgmt.resourcegraph import ResourceGraphClient
    from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions
    
    logger.info("Getting patch installation history: sub=%s, days=%d, rg=%s", 
                subscription_id, days, resource_group)
    
    try:
        credential = get_credential()
        arg_client = ResourceGraphClient(credential)
        
        # KQL query from Azure Update Manager
        query = f"""
        PatchInstallationResources
        | where properties.lastModifiedDateTime > ago({days}d)
        | where type in~ ("microsoft.compute/virtualmachines/patchinstallationresults", "microsoft.hybridcompute/machines/patchinstallationresults")
        | parse tolower(id) with resourceId "/patchinstallationresults" *
        | extend resourceId=tolower(resourceId), resourceType = strcat(split(type, "/")[0], "/", split(type, "/")[1])
        | join kind=leftouter(
            resources
            | where type in~ ("Microsoft.SqlVirtualMachine/sqlVirtualMachines", "microsoft.azurearcdata/sqlserverinstances")
            | project resourceId = iff(type =~ "Microsoft.SqlVirtualMachine/sqlVirtualMachines", tolower(properties.virtualMachineResourceId), tolower(properties.containerResourceId)), sqlType = type
            | summarize by resourceId, sqlType
        ) on resourceId
        | extend resourceType = iff(isnotempty(sqlType), sqlType, resourceType)
        | project id, type, properties, resourceType, resourceId
        | where resourceType in~ ("microsoft.compute/virtualmachines", "microsoft.hybridcompute/machines", "microsoft.sqlvirtualmachine/sqlvirtualmachines", "microsoft.azurearcdata/sqlserverinstances")
        """
        
        # Add resource group filter if specified
        if resource_group:
            query += f"\n| where resourceId contains '{resource_group.lower()}'"
        
        query += """
        | extend 
            vmName = tostring(split(resourceId, '/')[8]),
            resourceGroupName = tostring(split(resourceId, '/')[4]),
            osType = tostring(properties.osType),
            startedBy = tostring(properties.startedBy),
            status = tostring(properties.status),
            maintenanceRunId = tostring(properties.maintenanceRunId),
            isAutoPatching = isempty(properties.maintenanceRunId),
            startTime = todatetime(properties.startDateTime),
            endTime = todatetime(properties.lastModifiedDateTime),
            installedPatchCount = toint(properties.installedPatchCount),
            failedPatchCount = toint(properties.failedPatchCount),
            pendingPatchCount = toint(properties.pendingPatchCount),
            excludedPatchCount = toint(properties.excludedPatchCount),
            notSelectedPatchCount = toint(properties.notSelectedPatchCount),
            rebootStatus = tostring(properties.rebootStatus)
        | project vmName, resourceGroupName, osType, startedBy, status, maintenanceRunId, isAutoPatching, 
                  startTime, endTime, installedPatchCount, failedPatchCount, pendingPatchCount, 
                  excludedPatchCount, notSelectedPatchCount, rebootStatus, resourceType
        | order by startTime desc
        """
        
        # Execute query
        request = QueryRequest(
            subscriptions=[subscription_id],
            query=query,
            options=QueryRequestOptions(result_format="objectArray")
        )
        
        response = arg_client.resources(request)
        
        # Process results
        installations = []
        if response.data:
            installations = list(response.data)
        
        # Generate statistics
        stats = {
            "total_installations": len(installations),
            "by_status": {},
            "by_os": {},
            "by_starter": {},
            "maintenance_runs": 0,
            "auto_patching_runs": 0
        }
        
        for install in installations:
            # Status stats
            status = install.get('status', 'Unknown')
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # OS stats
            os_type = install.get('osType', 'Unknown')
            stats["by_os"][os_type] = stats["by_os"].get(os_type, 0) + 1
            
            # Starter stats
            starter = install.get('startedBy', 'Unknown')
            stats["by_starter"][starter] = stats["by_starter"].get(starter, 0) + 1
            
            # Patching type
            if install.get('isAutoPatching'):
                stats["auto_patching_runs"] += 1
            else:
                stats["maintenance_runs"] += 1
        
        result = {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "days_of_history": days,
            "statistics": stats,
            "installations": installations[:50]  # Limit to 50 most recent
        }
        
        if len(installations) > 50:
            result["note"] = f"Showing 50 most recent installations out of {len(installations)} total"
        
        return result
        
    except Exception as e:
        logger.exception("Failed to get patch installation history")
        return {
            "subscription_id": subscription_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "note": "Make sure azure-mgmt-resourcegraph package is installed and you have permissions to query Azure Resource Graph"
        }


def get_maintenance_config_with_vm_status(
    subscription_id: str,
    resource_group: str = None,
    configuration_name: str = None
) -> Dict[str, Any]:
    """
    Get maintenance configuration(s) with all associated VMs and their patch status.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Optional resource group to filter configs
        configuration_name: Optional specific configuration name
        
    Returns:
        Dict with maintenance configs and VM patch status
    """
    from azure.mgmt.maintenance import MaintenanceManagementClient
    from azure.mgmt.compute import ComputeManagementClient
    from azure.core.exceptions import ResourceNotFoundError
    
    logger.info("Getting maintenance config with VM status: sub=%s, rg=%s, config=%s", 
                subscription_id, resource_group, configuration_name)
    
    try:
        credential = get_credential()
        maintenance_client = MaintenanceManagementClient(credential, subscription_id)
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get maintenance configurations
        configurations = []
        if configuration_name and resource_group:
            try:
                config = maintenance_client.maintenance_configurations.get(
                    resource_group_name=resource_group,
                    resource_name=configuration_name
                )
                configurations = [config]
            except ResourceNotFoundError:
                return {"error": f"Configuration '{configuration_name}' not found"}
        else:
            configs = maintenance_client.maintenance_configurations.list()
            all_configs = list(configs)
            
            if resource_group:
                configurations = [c for c in all_configs 
                                if c.id.split('/')[4].lower() == resource_group.lower()]
            else:
                configurations = all_configs
        
        result = {
            "subscription_id": subscription_id,
            "configurations": []
        }
        
        # Get list of all VMs in subscription to check for assignments
        from azure.mgmt.compute import ComputeManagementClient as ComputeClient
        compute_for_vms = ComputeClient(credential, subscription_id)
        
        # Get all VMs in the subscription or resource group
        if resource_group:
            all_vms = list(compute_for_vms.virtual_machines.list(resource_group_name=resource_group))
        else:
            all_vms = list(compute_for_vms.virtual_machines.list_all())
        
        logger.info(f"Found {len(all_vms)} VMs to check for assignments")
        
        # Process each configuration
        for config in configurations:
            config_rg = config.id.split('/')[4]
            
            # Get VMs associated with this configuration
            vms = []
            try:
                # Check each VM for assignments to this configuration
                for vm in all_vms:
                    vm_rg = vm.id.split('/')[4]
                    vm_name = vm.name
                    
                    try:
                        # Get configuration assignments for this VM
                        assignments = maintenance_client.configuration_assignments.list(
                            resource_group_name=vm_rg,
                            provider_name="Microsoft.Compute",
                            resource_type="virtualMachines",
                            resource_name=vm_name
                        )
                        
                        # Check if any assignment matches our configuration
                        for assignment in assignments:
                            if config.name.lower() in assignment.maintenance_configuration_id.lower():
                                # Found a match! Get VM patch status
                                try:
                                    vm_info = compute_client.virtual_machines.get(
                                        resource_group_name=vm_rg,
                                        vm_name=vm_name,
                                        expand="instanceView"
                                    )
                                    
                                    vm_resource_id = vm_info.id  # Get full resource ID for ARG query
                                    instance_view = vm_info.instance_view
                                    patch_status = instance_view.patch_status if hasattr(instance_view, 'patch_status') else None
                                    
                                    vm_data = {
                                        "vm_name": vm_name,
                                        "resource_group": vm_rg,
                                        "power_state": next((s.display_status for s in instance_view.statuses if 'PowerState' in s.code), "Unknown") if instance_view else "Unknown"
                                    }
                                    
                                    # Check if patch status information is available
                                    if patch_status:
                                        available_patches = patch_status.available_patch_summary
                                        last_installation = patch_status.last_patch_installation_summary
                                        
                                        # Build patch status with available information
                                        patch_info = {}
                                        
                                        # Available patches information
                                        if available_patches:
                                            patch_info["available_patches"] = {
                                                "critical_and_security": getattr(available_patches, 'critical_and_security_patch_count', 0),
                                                "other": getattr(available_patches, 'other_patch_count', 0),
                                                "assessment_status": getattr(available_patches, 'status', 'Unknown'),
                                                "assessment_time": str(getattr(available_patches, 'assessment_activity_id', 'N/A')),
                                                "reboot_pending": getattr(available_patches, 'reboot_pending', False)
                                            }
                                        
                                        # Last installation information - get reboot status from ARG
                                        if last_installation:
                                            last_install_info = {
                                                "status": getattr(last_installation, 'status', 'Unknown'),
                                                "start_time": str(last_installation.start_time) if hasattr(last_installation, 'start_time') and last_installation.start_time else None,
                                                "installed_patches": getattr(last_installation, 'installed_patch_count', 0),
                                                "failed_patches": getattr(last_installation, 'failed_patch_count', 0),
                                                "pending_patches": getattr(last_installation, 'pending_patch_count', 0),
                                                "reboot_status": "Unknown"
                                            }
                                            
                                            # Get reboot status from ARG for accurate data
                                            try:
                                                from azure.mgmt.resourcegraph import ResourceGraphClient
                                                from azure.mgmt.resourcegraph.models import QueryRequest
                                                
                                                arg_client = ResourceGraphClient(credential)
                                                reboot_query = f"""
                                                PatchInstallationResources
                                                | where type =~ "microsoft.compute/virtualmachines/patchinstallationresults"
                                                | parse tolower(id) with resourceId "/patchinstallationresults" *
                                                | where resourceId =~ '{vm_resource_id.lower()}'
                                                | project 
                                                    rebootStatus = tostring(properties.rebootStatus),
                                                    lastModified = todatetime(properties.lastModifiedDateTime)
                                                | order by lastModified desc
                                                | take 1
                                                """
                                                reboot_request = QueryRequest(subscriptions=[subscription_id], query=reboot_query)
                                                reboot_response = arg_client.resources(reboot_request)
                                                
                                                if reboot_response.data and len(reboot_response.data) > 0:
                                                    last_install_info["reboot_status"] = reboot_response.data[0].get('rebootStatus', 'Unknown')
                                            except Exception as e:
                                                logger.warning(f"Could not get reboot status from ARG for {vm_name}: {e}")
                                            
                                            patch_info["last_installation"] = last_install_info
                                        
                                        vm_data["patch_status"] = patch_info if patch_info else "No patch data available"
                                    else:
                                        vm_data["patch_status"] = "Not Available"
                                    
                                    vms.append(vm_data)
                                    break  # Found assignment, no need to check other assignments for this VM
                                    
                                except Exception as vm_error:
                                    logger.warning("Failed to get status for VM %s: %s", vm_name, vm_error)
                                    vms.append({
                                        "vm_name": vm_name,
                                        "resource_group": vm_rg,
                                        "error": f"Failed to get patch status: {str(vm_error)}"
                                    })
                                    break
                                    
                    except Exception as e:
                        # No assignments for this VM, skip silently
                        pass
                                
            except Exception as e:
                logger.warning("Failed to check VM assignments for config %s: %s", config.name, e)
            
            config_data = {
                "name": config.name,
                "resource_group": config_rg,
                "location": config.location,
                "maintenance_scope": config.maintenance_scope,
                "visibility": getattr(config, 'visibility', None),
                "schedule": {
                    "start_time": str(getattr(config, 'start_date_time', None)),
                    "expiration_time": str(getattr(config, 'expiration_date_time', None)),
                    "duration": getattr(config, 'duration', None),
                    "time_zone": getattr(config, 'time_zone', None),
                    "recurrence": getattr(config, 'recur_every', None)
                },
                "associated_vms": vms,
                "total_vms": len(vms)
            }
            
            result["configurations"].append(config_data)
        
        result["total_configurations"] = len(configurations)
        return result
        
    except Exception as e:
        logger.exception("Failed to get maintenance config with VM status")
        return {
            "subscription_id": subscription_id,
            "error": str(e),
            "error_type": type(e).__name__
        }


def get_vm_patch_status_json(
    subscription_id: str,
    resource_group: str = None,
    configuration_name: str = None
) -> Dict[str, Any]:
    """
    Get VM patch assessment status in structured JSON format.
    Returns a simple list of VMs with their status for easy parsing.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Optional resource group name
        configuration_name: Optional maintenance configuration name
        
    Returns:
        Dict with:
        - vms: List of VM objects with name, resource_group, assessment_status, power_state
        - failed_vms: List of VMs with Failed assessment status
        - total_vms: Count of VMs
    """
    logger.info("Getting VM patch status in JSON format: sub=%s, rg=%s, config=%s",
                subscription_id, resource_group, configuration_name)
    
    try:
        # Use existing function to get full data
        full_data = get_maintenance_config_with_vm_status(
            subscription_id=subscription_id,
            resource_group=resource_group,
            configuration_name=configuration_name
        )
        
        if "error" in full_data:
            return full_data
        
        # Extract and simplify VM data
        vms = []
        failed_vms = []
        
        for config in full_data.get("configurations", []):
            for vm_data in config.get("associated_vms", []):
                # Extract key information
                vm_info = {
                    "vm_name": vm_data.get("vm_name"),
                    "resource_group": vm_data.get("resource_group"),
                    "power_state": vm_data.get("power_state", "unknown"),
                    "assessment_status": "unknown",
                    "available_patches": 0,
                    "critical_patches": 0
                }
                
                # Get assessment status from patch_status
                patch_status = vm_data.get("patch_status", {})
                if isinstance(patch_status, dict):
                    available = patch_status.get("available_patches", {})
                    if isinstance(available, dict):
                        vm_info["assessment_status"] = available.get("assessment_status", "unknown")
                        vm_info["critical_patches"] = available.get("critical_and_security", 0)
                        vm_info["available_patches"] = available.get("other", 0) + vm_info["critical_patches"]
                
                vms.append(vm_info)
                
                # Track failed VMs
                if vm_info["assessment_status"].lower() == "failed":
                    failed_vms.append(vm_info)
        
        return {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "configuration_name": configuration_name,
            "vms": vms,
            "failed_vms": failed_vms,
            "total_vms": len(vms),
            "failed_count": len(failed_vms)
        }
        
    except Exception as e:
        logger.exception("Failed to get VM patch status JSON")
        return {
            "subscription_id": subscription_id,
            "error": str(e),
            "error_type": type(e).__name__
        }


# ------------------------------------------------
# REQUIRED: FunctionTool mapping
# ------------------------------------------------

# Import diagnostic functions
from vmstatusagent.diagnostic_functions import (
    get_vm_boot_diagnostics,
    get_vm_extension_status,
    get_vm_guest_agent_status,
    diagnose_patch_failure
)

# Import remediation functions
from vmstatusagent.remediation_functions import (
    search_knowledge_base,
    extract_remediation_steps,
    generate_remediation_plan,
    save_remediation_result,
    get_remediation_history
)

user_functions = {
    # Patch Status Agent Functions
    "get_maintenance_configuration_details": get_maintenance_configuration_details,
    "get_maintenance_config_with_vm_status": get_maintenance_config_with_vm_status,
    "get_patch_installation_history": get_patch_installation_history,
    "get_vm_patch_status_json": get_vm_patch_status_json,  # NEW: Structured JSON output
    
    # Diagnostic Agent Functions
    "get_vm_boot_diagnostics": get_vm_boot_diagnostics,
    "get_vm_extension_status": get_vm_extension_status,
    "get_vm_guest_agent_status": get_vm_guest_agent_status,
    "diagnose_patch_failure": diagnose_patch_failure,
    
    # Remediation Agent Functions
    "search_knowledge_base": search_knowledge_base,
    "extract_remediation_steps": extract_remediation_steps,
    "generate_remediation_plan": generate_remediation_plan,
    "save_remediation_result": save_remediation_result,
    "get_remediation_history": get_remediation_history,
}
 
__all__ = list(user_functions.keys())