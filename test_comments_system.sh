#!/bin/bash

# ============================================================================
# COMMENTS SYSTEM - VERIFICATION TEST SCRIPT
# Run this script to verify the comments system is properly set up
# ============================================================================

echo "🧪 BRANDING GATE - COMMENTS SYSTEM VERIFICATION"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Test function
test_check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((FAILED++))
    fi
}

echo "📊 DATABASE TESTS"
echo "-------------------"

# Test 1: Check if comments table exists
mysql -u ps -p'Aa@123456' branding_gate -e "DESCRIBE sales_request_comments;" > /dev/null 2>&1
test_check $? "Table 'sales_request_comments' exists"

# Test 2: Check if mentions table exists
mysql -u ps -p'Aa@123456' branding_gate -e "DESCRIBE sales_request_comment_mentions;" > /dev/null 2>&1
test_check $? "Table 'sales_request_comment_mentions' exists"

# Test 3: Check comments table structure
COLUMNS=$(mysql -u ps -p'Aa@123456' branding_gate -e "SHOW COLUMNS FROM sales_request_comments;" 2>/dev/null | wc -l)
if [ $COLUMNS -ge 12 ]; then
    test_check 0 "Comments table has all required columns ($COLUMNS columns)"
else
    test_check 1 "Comments table missing columns (found $COLUMNS, expected 12+)"
fi

# Test 4: Check mentions table structure
COLUMNS=$(mysql -u ps -p'Aa@123456' branding_gate -e "SHOW COLUMNS FROM sales_request_comment_mentions;" 2>/dev/null | wc -l)
if [ $COLUMNS -ge 5 ]; then
    test_check 0 "Mentions table has all required columns ($COLUMNS columns)"
else
    test_check 1 "Mentions table missing columns (found $COLUMNS, expected 5+)"
fi

# Test 5: Check foreign keys
FK_COUNT=$(mysql -u ps -p'Aa@123456' branding_gate -e "SELECT COUNT(*) as count FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_TYPE = 'FOREIGN KEY' AND TABLE_NAME = 'sales_request_comments';" 2>/dev/null | tail -1)
if [ "$FK_COUNT" -ge 3 ]; then
    test_check 0 "Foreign keys configured ($FK_COUNT found)"
else
    test_check 1 "Foreign keys missing (found $FK_COUNT, expected 3+)"
fi

# Test 6: Check indexes
INDEX_COUNT=$(mysql -u ps -p'Aa@123456' branding_gate -e "SHOW INDEX FROM sales_request_comments;" 2>/dev/null | wc -l)
if [ $INDEX_COUNT -ge 5 ]; then
    test_check 0 "Indexes created ($INDEX_COUNT found)"
else
    test_check 1 "Indexes missing (found $INDEX_COUNT, expected 5+)"
fi

echo ""
echo "📁 FILE TESTS"
echo "-------------------"

# Test 7: Check widget file exists
if [ -f "templates/comments_widget.html" ]; then
    test_check 0 "Widget file 'comments_widget.html' exists"
else
    test_check 1 "Widget file 'comments_widget.html' NOT FOUND"
fi

# Test 8: Check documentation exists
if [ -f "COMMENTS_SYSTEM_DOCUMENTATION.md" ]; then
    test_check 0 "Documentation file exists"
else
    test_check 1 "Documentation file NOT FOUND"
fi

# Test 9: Check integration example exists
if [ -f "INTEGRATION_EXAMPLE.html" ]; then
    test_check 0 "Integration example exists"
else
    test_check 1 "Integration example NOT FOUND"
fi

echo ""
echo "🔧 BACKEND TESTS"
echo "-------------------"

# Test 10: Check if API endpoints are in branding_gate.py
if grep -q "def get_request_comments" branding_gate.py; then
    test_check 0 "API endpoint 'get_request_comments' found"
else
    test_check 1 "API endpoint 'get_request_comments' NOT FOUND"
fi

if grep -q "def add_request_comment" branding_gate.py; then
    test_check 0 "API endpoint 'add_request_comment' found"
else
    test_check 1 "API endpoint 'add_request_comment' NOT FOUND"
fi

if grep -q "def search_users_for_mention" branding_gate.py; then
    test_check 0 "API endpoint 'search_users_for_mention' found"
else
    test_check 1 "API endpoint 'search_users_for_mention' NOT FOUND"
fi

if grep -q "def get_my_mentions" branding_gate.py; then
    test_check 0 "API endpoint 'get_my_mentions' found"
else
    test_check 1 "API endpoint 'get_my_mentions' NOT FOUND"
fi

echo ""
echo "🌐 FRONTEND TESTS"
echo "-------------------"

# Test 11: Check widget has required functions
if grep -q "function initCommentsWidget" templates/comments_widget.html; then
    test_check 0 "JavaScript function 'initCommentsWidget' found"
else
    test_check 1 "JavaScript function 'initCommentsWidget' NOT FOUND"
fi

if grep -q "function postComment" templates/comments_widget.html; then
    test_check 0 "JavaScript function 'postComment' found"
else
    test_check 1 "JavaScript function 'postComment' NOT FOUND"
fi

if grep -q "function searchUsersForMention" templates/comments_widget.html; then
    test_check 0 "JavaScript function 'searchUsersForMention' found"
else
    test_check 1 "JavaScript function 'searchUsersForMention' NOT FOUND"
fi

# Test 12: Check CSS styles exist
if grep -q ".comments-widget" templates/comments_widget.html; then
    test_check 0 "CSS styles for widget found"
else
    test_check 1 "CSS styles for widget NOT FOUND"
fi

echo ""
echo "🔍 DATA TESTS"
echo "-------------------"

# Test 13: Try to insert a test comment (will be deleted)
TEST_INSERT=$(mysql -u ps -p'Aa@123456' branding_gate -e "INSERT INTO sales_request_comments (request_id, user_id, comment_text, source) VALUES (1, 1, 'Test comment - verification', 'general'); SELECT LAST_INSERT_ID();" 2>&1)

if echo "$TEST_INSERT" | grep -qE "[0-9]+"; then
    test_check 0 "Can insert comments into database"
    # Clean up test data
    TEST_ID=$(echo "$TEST_INSERT" | tail -1)
    mysql -u ps -p'Aa@123456' branding_gate -e "DELETE FROM sales_request_comments WHERE id = $TEST_ID;" 2>/dev/null
else
    test_check 1 "Cannot insert comments into database"
fi

# Test 14: Check if notifications table exists (for mention notifications)
mysql -u ps -p'Aa@123456' branding_gate -e "DESCRIBE notifications;" > /dev/null 2>&1
test_check $? "Notifications table exists (for mention alerts)"

echo ""
echo "📊 SUMMARY"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo "Total Tests: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo ""
    echo "✅ Comments system is fully set up and ready to use!"
    echo ""
    echo "📋 NEXT STEPS:"
    echo "1. Restart Flask application: python branding_gate.py"
    echo "2. Add {% include 'comments_widget.html' %} to your pages"
    echo "3. Initialize with: initCommentsWidget(requestId, 'general')"
    echo "4. Test in browser"
    echo ""
    echo "📚 DOCUMENTATION:"
    echo "- COMMENTS_SYSTEM_DOCUMENTATION.md - Full documentation"
    echo "- INTEGRATION_EXAMPLE.html - Integration guide"
    echo "- COMMENTS_QUICK_REFERENCE.md - Quick reference"
    exit 0
else
    echo -e "${RED}⚠️  SOME TESTS FAILED${NC}"
    echo ""
    echo "Please review the failed tests above and fix any issues."
    echo ""
    echo "Common fixes:"
    echo "- Run: mysql -u ps -p'Aa@123456' branding_gate < create_comments_system.sql"
    echo "- Ensure branding_gate.py has been updated with new endpoints"
    echo "- Check that templates/comments_widget.html exists"
    exit 1
fi
