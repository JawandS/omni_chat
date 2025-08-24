#!/usr/bin/env python3
"""
Test script for Gemini 2.5 Pro with live search functionality.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the path so we can import from chat.py
sys.path.insert(0, os.path.dirname(__file__))

from chat import _gemini_live_call, get_api_key

def test_gemini_live_search():
    """Test the Gemini live search functionality."""
    
    # Check if API key is available
    api_key = get_api_key("gemini")
    if not api_key or api_key.startswith("PUT_"):
        print("❌ Gemini API key not found. Please set GEMINI_API_KEY in your .env file.")
        return False
    
    print("🔑 Gemini API key found")
    
    # Test queries that would benefit from live search
    test_queries = [
        "What is the current inflation rate in the United States?",
        "What are the latest developments in AI technology this week?",
        "What is the current price of Bitcoin?"
    ]
    
    print(f"\n🧪 Testing Gemini 2.5 Pro Live Search with {len(test_queries)} queries...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Test {i}: {query} ---")
        
        try:
            # Call the live search function
            response = _gemini_live_call(
                model="gemini-2.5-pro-live",
                history=[],
                message=query
            )
            
            if response:
                print(f"✅ Response received ({len(response)} characters)")
                print(f"📝 Preview: {response[:200]}...")
                
                # Check if sources are included
                if "**Sources:**" in response:
                    print("🔗 Sources included in response")
                else:
                    print("ℹ️  No sources found in response")
            else:
                print("❌ No response received")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n✅ Gemini live search test completed!")
    return True

if __name__ == "__main__":
    test_gemini_live_search()
