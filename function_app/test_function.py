#!/usr/bin/env python3
"""
Test the Azure Function App agent gateway
"""
import requests
import json

# Base URL - change this when deployed to Azure
BASE_URL = "http://localhost:7071/api"

def test_health():
    """Test health endpoint"""
    print("=" * 60)
    print("Testing Health Endpoint")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_agent_post():
    """Test agent query via POST"""
    print("=" * 60)
    print("Testing Agent Query (POST)")
    print("=" * 60)
    
    payload = {
        "query": "Show me maintenance configurations in resource group rg-cp-ravindra-vancharla"
    }
    
    response = requests.post(
        f"{BASE_URL}/agent/query",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_agent_get():
    """Test agent query via GET"""
    print("=" * 60)
    print("Testing Agent Chat (GET)")
    print("=" * 60)
    
    params = {
        "q": "Show me maintenance configurations in rg-cp-ravindra-vancharla"
    }
    
    response = requests.get(f"{BASE_URL}/agent/chat", params=params)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_identity():
    """Test identity endpoint"""
    print("=" * 60)
    print("Testing Identity Endpoint")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/debug/identity")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


if __name__ == "__main__":
    print("\n🚀 Testing Azure Function App - Agent Gateway\n")
    
    try:
        test_health()
        test_identity()
        test_agent_post()
        # test_agent_get()  # Alternative GET-based interface
        
        print("✅ All tests completed!\n")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to Function App")
        print("Make sure the function app is running: func start\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
