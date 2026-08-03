#!/usr/bin/env python3
"""
Test script to verify operation status logic
"""

def calculate_status(total_items, costed_items):
    """Calculate status based on item counts"""
    if total_items == 0:
        return 'No Items'
    elif costed_items == 0:
        return 'Pending'
    elif costed_items == total_items:
        return 'Completed'
    else:
        return 'Pending'  # Partially costed - still pending

# Test cases
test_cases = [
    (0, 0, 'No Items'),      # No items at all
    (3, 0, 'Pending'),       # 0/3 items costed
    (3, 1, 'Pending'),       # 1/3 items costed (partial)
    (3, 2, 'Pending'),       # 2/3 items costed (partial)
    (3, 3, 'Completed'),     # 3/3 items costed (complete)
    (1, 1, 'Completed'),     # 1/1 items costed (complete)
    (5, 4, 'Pending'),       # 4/5 items costed (partial)
]

print("Testing operation status logic:")
print("=" * 50)

for total_items, costed_items, expected in test_cases:
    result = calculate_status(total_items, costed_items)
    status = "✅ PASS" if result == expected else "❌ FAIL"
    print(f"{status} | {costed_items}/{total_items} items → '{result}' (expected: '{expected}')")

print("\nStatus logic test completed!")
