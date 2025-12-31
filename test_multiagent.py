#!/usr/bin/env python3
"""
Test script for multi-agent patch management system
Tests individual functions and end-to-end orchestration
"""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from vmstatusagent.diagnostic_functions import (
    get_vm_boot_diagnostics,
    get_vm_extension_status,
    get_vm_guest_agent_status,
    diagnose_patch_failure
)

from vmstatusagent.remediation_functions import (
    search_knowledge_base,
    extract_remediation_steps,
    generate_remediation_plan,
    get_remediation_history
)

def test_diagnostic_functions():
    """Test diagnostic agent functions"""
    print("\n" + "="*80)
    print("Testing Diagnostic Agent Functions")
    print("="*80)
    
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "343c17eb-34b6-4481-92a2-a0a5a04bdd88")
    resource_group = "rg-cp-ravindra-vancharla"
    vm_name = "ubuntutestserver"
    
    # Test 1: Boot diagnostics
    print("\n[TEST 1] get_vm_boot_diagnostics()")
    try:
        result = get_vm_boot_diagnostics(subscription_id, resource_group, vm_name)
        print(f"✓ Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {str(e)}")
    
    # Test 2: Extension status
    print("\n[TEST 2] get_vm_extension_status()")
    try:
        result = get_vm_extension_status(subscription_id, resource_group, vm_name)
        print(f"✓ Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {str(e)}")
    
    # Test 3: Guest agent status
    print("\n[TEST 3] get_vm_guest_agent_status()")
    try:
        result = get_vm_guest_agent_status(subscription_id, resource_group, vm_name)
        print(f"✓ Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {str(e)}")
    
    # Test 4: Comprehensive diagnostics
    print("\n[TEST 4] diagnose_patch_failure()")
    try:
        result = diagnose_patch_failure(subscription_id, resource_group, vm_name, "Failed")
        print(f"✓ Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {str(e)}")


def test_remediation_functions():
    """Test remediation agent functions"""
    print("\n" + "="*80)
    print("Testing Remediation Agent Functions")
    print("="*80)
    
    vm_name = "ubuntutestserver"
    resource_group = "rg-cp-ravindra-vancharla"
    
    # Test 1: Search knowledge base
    print("\n[TEST 1] search_knowledge_base()")
    try:
        result = search_knowledge_base(
            vm_name=vm_name,
            assessment_status="Failed",
            max_results=5
        )
        print(f"✓ Success: Found {result.get('total_results', 0)} results")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"✗ Failed: {str(e)}")
    
    # Test 2: Extract remediation steps (using mock KB results)
    print("\n[TEST 2] extract_remediation_steps()")
    try:
        mock_kb_results = [
            {
                "response": "VM requires reboot to complete pending updates. Assessment status: Failed",
                "timestamp": "2025-12-23T10:00:00Z"
            },
            {
                "response": "Guest agent not ready. Extension errors detected. Assessment failed.",
                "timestamp": "2025-12-23T09:00:00Z"
            }
        ]
        result = extract_remediation_steps(mock_kb_results)
        print(f"✓ Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {str(e)}")
    
    # Test 3: Generate remediation plan
    print("\n[TEST 3] generate_remediation_plan()")
    try:
        mock_diagnostic_results = {
            "issues_found": [
                "VM Guest Agent not in Ready state",
                "Found 1 extension(s) with errors"
            ],
            "recommendations": [
                "Check guest agent logs and restart VM if needed",
                "Review VM event logs for patch installation errors"
            ]
        }
        
        mock_kb_search = {
            "results": [
                {"response": "Reboot required for failed assessment", "timestamp": "2025-12-23T10:00:00Z"}
            ]
        }
        
        result = generate_remediation_plan(
            vm_name=vm_name,
            resource_group=resource_group,
            diagnostic_results=mock_diagnostic_results,
            kb_search_results=mock_kb_search
        )
        print(f"✓ Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {str(e)}")
    
    # Test 4: Get remediation history
    print("\n[TEST 4] get_remediation_history()")
    try:
        result = get_remediation_history(
            vm_name=vm_name,
            resource_group=resource_group,
            days=30,
            max_results=10
        )
        print(f"✓ Success: Found {result.get('total_results', 0)} historical remediations")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"✗ Failed: {str(e)}")


def test_function_registration():
    """Test that all functions are properly registered"""
    print("\n" + "="*80)
    print("Testing Function Registration")
    print("="*80)
    
    from vmstatusagent.user_functions import user_functions
    
    expected_functions = [
        # Patch Status
        "get_maintenance_configuration_details",
        "get_maintenance_config_with_vm_status",
        "get_patch_installation_history",
        # Diagnostic
        "get_vm_boot_diagnostics",
        "get_vm_extension_status",
        "get_vm_guest_agent_status",
        "diagnose_patch_failure",
        # Remediation
        "search_knowledge_base",
        "extract_remediation_steps",
        "generate_remediation_plan",
        "save_remediation_result",
        "get_remediation_history",
    ]
    
    print(f"\nExpected {len(expected_functions)} functions")
    print(f"Registered {len(user_functions)} functions\n")
    
    for func_name in expected_functions:
        if func_name in user_functions:
            print(f"✓ {func_name}")
        else:
            print(f"✗ {func_name} - MISSING!")
    
    # Check for unexpected functions
    extra_functions = set(user_functions.keys()) - set(expected_functions)
    if extra_functions:
        print(f"\nExtra functions found: {extra_functions}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("Multi-Agent Patch Management System - Test Suite")
    print("="*80)
    
    # Test 1: Function registration
    test_function_registration()
    
    # Test 2: Diagnostic functions (requires Azure credentials)
    print("\n\nNote: The following tests require Azure credentials and may fail if:")
    print("  - Azure credentials are not configured")
    print("  - VMs don't exist")
    print("  - Storage account is not accessible")
    
    response = input("\nRun Azure integration tests? (y/n): ")
    if response.lower() == 'y':
        test_diagnostic_functions()
        test_remediation_functions()
    else:
        print("\nSkipping Azure integration tests.")
    
    print("\n" + "="*80)
    print("Test suite completed")
    print("="*80)


if __name__ == "__main__":
    main()
