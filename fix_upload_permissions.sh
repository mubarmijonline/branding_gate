#!/bin/bash

# Fix Upload Directory Permissions for Branding Gate
# This script fixes permissions so the web server can upload files

echo "========================================="
echo "Branding Gate - Fix Upload Permissions"
echo "========================================="
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Warning: This script needs sudo privileges to fix permissions${NC}"
    echo "Please run with: sudo ./fix_upload_permissions.sh"
    exit 1
fi

echo "Step 1: Creating uploads/items directory..."
mkdir -p uploads/items
echo -e "${GREEN}✓ Directory created${NC}"
echo ""

echo "Step 2: Detecting web server user..."
# Try to detect web server user
WEB_USER=""
if id "www-data" &>/dev/null; then
    WEB_USER="www-data"
elif id "nginx" &>/dev/null; then
    WEB_USER="nginx"
elif id "apache" &>/dev/null; then
    WEB_USER="apache"
else
    echo -e "${YELLOW}Could not auto-detect web server user${NC}"
    echo "Common users: www-data, nginx, apache"
    read -p "Enter web server username: " WEB_USER
    
    if ! id "$WEB_USER" &>/dev/null; then
        echo -e "${RED}✗ User '$WEB_USER' does not exist${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Using web server user: $WEB_USER${NC}"
echo ""

echo "Step 3: Setting ownership..."
# Set ownership to web server user
chown -R $WEB_USER:$WEB_USER uploads/items/
echo -e "${GREEN}✓ Ownership set to $WEB_USER:$WEB_USER${NC}"
echo ""

echo "Step 4: Setting directory permissions..."
# Set directory permissions to 755 (rwxr-xr-x)
find uploads/items/ -type d -exec chmod 755 {} \;
echo -e "${GREEN}✓ Directory permissions set to 755${NC}"
echo ""

echo "Step 5: Setting file permissions..."
# Set file permissions to 644 (rw-r--r--)
find uploads/items/ -type f -exec chmod 644 {} \;
echo -e "${GREEN}✓ File permissions set to 644${NC}"
echo ""

echo "Step 6: Making items directory writable..."
# Give web server write access to items directory
chmod 775 uploads/items/
echo -e "${GREEN}✓ Items directory is now writable${NC}"
echo ""

echo "Step 7: Setting setgid bit (optional, for shared access)..."
# Set setgid bit so new files inherit group ownership
chmod g+s uploads/items/
echo -e "${GREEN}✓ setgid bit set${NC}"
echo ""

echo "========================================="
echo "Verification"
echo "========================================="
echo ""
echo "Current permissions:"
ls -lah uploads/ | grep -E "items|companies|sales_requests"
echo ""

echo "Testing write access..."
TEST_FILE="uploads/items/.test_write_$$"
if sudo -u $WEB_USER touch "$TEST_FILE" 2>/dev/null; then
    echo -e "${GREEN}✓ Write test PASSED - $WEB_USER can write files${NC}"
    rm -f "$TEST_FILE"
else
    echo -e "${RED}✗ Write test FAILED - $WEB_USER cannot write files${NC}"
    echo "Please check permissions manually"
fi
echo ""

echo "========================================="
echo "Summary"
echo "========================================="
echo ""
echo "✓ Directory created: uploads/items/"
echo "✓ Owner: $WEB_USER:$WEB_USER"
echo "✓ Directory permissions: 755 (rwxr-xr-x)"
echo "✓ File permissions: 644 (rw-r--r--)"
echo "✓ Items directory: 775 (rwxrwxr-x)"
echo "✓ setgid bit enabled"
echo ""
echo -e "${GREEN}Permissions have been fixed!${NC}"
echo ""
echo "Next steps:"
echo "1. Restart your web server:"
echo "   sudo systemctl restart nginx"
echo "   # or"
echo "   sudo systemctl restart apache2"
echo ""
echo "2. Test file upload in the application"
echo ""
echo "3. Monitor logs for any permission errors:"
echo "   tail -f /var/log/nginx/error.log"
echo "   # or check Flask logs"
echo ""
