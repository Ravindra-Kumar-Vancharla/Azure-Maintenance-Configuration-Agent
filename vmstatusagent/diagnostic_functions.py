# vmstatusagent/diagnostic_functions.py
"""
Diagnostic Agent Functions - Deep dive into VM failures
 
These functions provide detailed diagnostic information when patch assessments fail.
"""
 
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from azure.mgmt.compute import ComputeManagementClient
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Shared credential function (avoid circular import)
_credential: Optional[DefaultAzureCredential] = None

def get_credential() -> DefaultAzureCredential:
    """
    Lazily create and cache Azure credential.
    """
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def get_vm_boot_diagnostics(
    subscription_id: str,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """
    Get VM boot diagnostics including serial console output and screenshot.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        vm_name: Virtual machine name
    
    Returns:
        Dict with boot diagnostic information
    """
    logger.info(
        "Getting boot diagnostics: sub=%s rg=%s vm=%s",
        subscription_id, resource_group, vm_name
    )
    
    try:
        credential = get_credential()
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get VM to check boot diagnostics status
        vm = compute_client.virtual_machines.get(
            resource_group_name=resource_group,
            vm_name=vm_name,
            expand="instanceView"
        )
        
        result = {
            "vm_name": vm_name,
            "resource_group": resource_group,
            "boot_diagnostics_enabled": False,
            "serial_console_available": False,
            "screenshot_available": False
        }
        
        # Check if boot diagnostics is enabled
        if vm.diagnostics_profile and vm.diagnostics_profile.boot_diagnostics:
            boot_diag = vm.diagnostics_profile.boot_diagnostics
            result["boot_diagnostics_enabled"] = boot_diag.enabled or False
            
            if boot_diag.enabled:
                result["storage_uri"] = boot_diag.storage_uri
                
                # Try to get boot diagnostics data
                try:
                    boot_diag_data = compute_client.virtual_machines.retrieve_boot_diagnostics_data(
                        resource_group_name=resource_group,
                        vm_name=vm_name
                    )
                    
                    result["serial_console_available"] = True
                    result["console_screenshot_blob_uri"] = boot_diag_data.console_screenshot_blob_uri
                    result["serial_console_log_blob_uri"] = boot_diag_data.serial_console_log_blob_uri
                    result["screenshot_available"] = True
                    
                except (ResourceNotFoundError, HttpResponseError) as e:
                    logger.warning("Could not retrieve boot diagnostics data: %s", str(e))
                    result["error"] = f"Boot diagnostics enabled but data unavailable: {str(e)}"
        else:
            result["message"] = "Boot diagnostics not enabled for this VM"
        
        # Get instance view statuses for additional diagnostic info
        if vm.instance_view:
            statuses = []
            for status in vm.instance_view.statuses:
                statuses.append({
                    "code": status.code,
                    "level": status.level,
                    "display_status": status.display_status,
                    "message": status.message if hasattr(status, 'message') else None,
                    "time": str(status.time) if hasattr(status, 'time') else None
                })
            result["vm_statuses"] = statuses
        
        return result
        
    except ResourceNotFoundError:
        return {
            "error": f"VM '{vm_name}' not found in resource group '{resource_group}'"
        }
    except Exception as e:
        logger.error("Error getting boot diagnostics: %s", str(e), exc_info=True)
        return {
            "error": f"Failed to get boot diagnostics: {str(e)}"
        }


def get_vm_extension_status(
    subscription_id: str,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """
    Get status of all VM extensions, especially patch-related ones.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        vm_name: Virtual machine name
    
    Returns:
        Dict with extension status information
    """
    logger.info(
        "Getting VM extension status: sub=%s rg=%s vm=%s",
        subscription_id, resource_group, vm_name
    )
    
    try:
        credential = get_credential()
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get VM with instance view to see extension statuses
        vm = compute_client.virtual_machines.get(
            resource_group_name=resource_group,
            vm_name=vm_name,
            expand="instanceView"
        )
        
        result = {
            "vm_name": vm_name,
            "resource_group": resource_group,
            "extensions": []
        }
        
        # Get extension details from instance view
        if vm.instance_view and vm.instance_view.extensions:
            for ext in vm.instance_view.extensions:
                ext_info = {
                    "name": ext.name,
                    "type": ext.type if hasattr(ext, 'type') else "Unknown",
                    "type_handler_version": ext.type_handler_version if hasattr(ext, 'type_handler_version') else "Unknown"
                }
                
                # Get status information
                if ext.statuses:
                    statuses = []
                    for status in ext.statuses:
                        statuses.append({
                            "code": status.code,
                            "level": status.level,
                            "display_status": status.display_status,
                            "message": status.message if hasattr(status, 'message') else None,
                            "time": str(status.time) if hasattr(status, 'time') else None
                        })
                    ext_info["statuses"] = statuses
                    
                    # Flag if extension has errors
                    ext_info["has_errors"] = any(
                        s.level and s.level.lower() == "error" for s in ext.statuses
                    )
                
                # Get substatuses if available
                if hasattr(ext, 'substatuses') and ext.substatuses:
                    substatuses = []
                    for substatus in ext.substatuses:
                        substatuses.append({
                            "code": substatus.code,
                            "level": substatus.level,
                            "display_status": substatus.display_status,
                            "message": substatus.message if hasattr(substatus, 'message') else None
                        })
                    ext_info["substatuses"] = substatuses
                
                result["extensions"].append(ext_info)
        
        # Identify patch-related extensions
        patch_extensions = [
            ext for ext in result["extensions"]
            if any(keyword in ext.get("name", "").lower() 
                   for keyword in ["patch", "update", "linux", "windows"])
        ]
        
        result["patch_extension_count"] = len(patch_extensions)
        result["total_extension_count"] = len(result["extensions"])
        result["extensions_with_errors"] = sum(
            1 for ext in result["extensions"] if ext.get("has_errors", False)
        )
        
        if not result["extensions"]:
            result["message"] = "No extensions installed on this VM"
        
        return result
        
    except ResourceNotFoundError:
        return {
            "error": f"VM '{vm_name}' not found in resource group '{resource_group}'"
        }
    except Exception as e:
        logger.error("Error getting extension status: %s", str(e), exc_info=True)
        return {
            "error": f"Failed to get extension status: {str(e)}"
        }


def get_vm_guest_agent_status(
    subscription_id: str,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """
    Get Azure VM Guest Agent status and version information.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        vm_name: Virtual machine name
    
    Returns:
        Dict with guest agent status
    """
    logger.info(
        "Getting guest agent status: sub=%s rg=%s vm=%s",
        subscription_id, resource_group, vm_name
    )
    
    try:
        credential = get_credential()
        compute_client = ComputeManagementClient(credential, subscription_id)
        
        # Get VM instance view
        vm = compute_client.virtual_machines.get(
            resource_group_name=resource_group,
            vm_name=vm_name,
            expand="instanceView"
        )
        
        result = {
            "vm_name": vm_name,
            "resource_group": resource_group,
            "guest_agent_installed": False
        }
        
        if vm.instance_view and vm.instance_view.vm_agent:
            vm_agent = vm.instance_view.vm_agent
            
            result["guest_agent_installed"] = True
            result["vm_agent_version"] = vm_agent.vm_agent_version
            
            # Get agent statuses
            if vm_agent.statuses:
                statuses = []
                for status in vm_agent.statuses:
                    statuses.append({
                        "code": status.code,
                        "level": status.level,
                        "display_status": status.display_status,
                        "message": status.message if hasattr(status, 'message') else None,
                        "time": str(status.time) if hasattr(status, 'time') else None
                    })
                result["statuses"] = statuses
                
                # Check if agent is ready
                result["agent_ready"] = any(
                    "ready" in s.display_status.lower() 
                    for s in vm_agent.statuses 
                    if s.display_status
                )
            
            # Get extension handler information
            if hasattr(vm_agent, 'extension_handlers') and vm_agent.extension_handlers:
                handlers = []
                for handler in vm_agent.extension_handlers:
                    handler_info = {
                        "type": handler.type if hasattr(handler, 'type') else "Unknown",
                        "type_handler_version": handler.type_handler_version if hasattr(handler, 'type_handler_version') else "Unknown"
                    }
                    
                    if hasattr(handler, 'status') and handler.status:
                        handler_info["status"] = {
                            "code": handler.status.code,
                            "level": handler.status.level,
                            "display_status": handler.status.display_status,
                            "message": handler.status.message if hasattr(handler.status, 'message') else None
                        }
                    
                    handlers.append(handler_info)
                
                result["extension_handlers"] = handlers
        else:
            result["message"] = "VM Guest Agent not installed or not reporting"
        
        return result
        
    except ResourceNotFoundError:
        return {
            "error": f"VM '{vm_name}' not found in resource group '{resource_group}'"
        }
    except Exception as e:
        logger.error("Error getting guest agent status: %s", str(e), exc_info=True)
        return {
            "error": f"Failed to get guest agent status: {str(e)}"
        }


def diagnose_patch_failure(
    subscription_id: str,
    resource_group: str,
    vm_name: str,
    assessment_status: str = None
) -> Dict[str, Any]:
    """
    Comprehensive diagnostic function that aggregates multiple diagnostic sources.
    Use this when a VM has patch assessment or installation failures.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        vm_name: Virtual machine name
        assessment_status: Optional assessment status (Failed, InProgress, etc.)
    
    Returns:
        Dict with comprehensive diagnostic information
    """
    logger.info(
        "Running comprehensive patch failure diagnostics: sub=%s rg=%s vm=%s status=%s",
        subscription_id, resource_group, vm_name, assessment_status
    )
    
    result = {
        "vm_name": vm_name,
        "resource_group": resource_group,
        "assessment_status": assessment_status,
        "diagnostics": {},
        "issues_found": [],
        "recommendations": []
    }
    
    # 1. Check boot diagnostics
    boot_diag = get_vm_boot_diagnostics(subscription_id, resource_group, vm_name)
    result["diagnostics"]["boot_diagnostics"] = boot_diag
    
    if boot_diag.get("error"):
        result["issues_found"].append(f"Boot diagnostics error: {boot_diag['error']}")
    elif not boot_diag.get("boot_diagnostics_enabled"):
        result["recommendations"].append("Enable boot diagnostics for better troubleshooting")
    
    # 2. Check extension status
    ext_status = get_vm_extension_status(subscription_id, resource_group, vm_name)
    result["diagnostics"]["extensions"] = ext_status
    
    if ext_status.get("extensions_with_errors", 0) > 0:
        result["issues_found"].append(
            f"Found {ext_status['extensions_with_errors']} extension(s) with errors"
        )
        # Add details about failed extensions
        for ext in ext_status.get("extensions", []):
            if ext.get("has_errors"):
                result["issues_found"].append(
                    f"Extension '{ext['name']}' has errors - check statuses for details"
                )
    
    # 3. Check guest agent status
    agent_status = get_vm_guest_agent_status(subscription_id, resource_group, vm_name)
    result["diagnostics"]["guest_agent"] = agent_status
    
    if not agent_status.get("guest_agent_installed"):
        result["issues_found"].append("VM Guest Agent not installed or not reporting")
        result["recommendations"].append("Install or repair Azure VM Guest Agent")
    elif not agent_status.get("agent_ready"):
        result["issues_found"].append("VM Guest Agent not in Ready state")
        result["recommendations"].append("Check guest agent logs and restart VM if needed")
    
    # 4. General recommendations based on assessment status
    if assessment_status:
        if assessment_status.lower() == "failed":
            result["recommendations"].extend([
                "Review VM event logs for patch installation errors",
                "Check if VM requires reboot after previous patch installation",
                "Verify VM has adequate disk space for patch downloads",
                "Ensure VM can reach Azure Update Management endpoints"
            ])
        elif assessment_status.lower() == "inprogress":
            result["recommendations"].append(
                "Assessment in progress - allow more time before troubleshooting"
            )
    
    # Summary
    result["summary"] = {
        "total_issues": len(result["issues_found"]),
        "total_recommendations": len(result["recommendations"]),
        "requires_attention": len(result["issues_found"]) > 0
    }
    
    return result
