#!/bin/bash
# ============================================
# SETUP SCRIPT FOR OTHER MACHINE
# ============================================
# Copy this script to the project folder and run it
# Usage: 
#   bash setup_other_machine.sh              # Uses script's directory
#   bash setup_other_machine.sh /path/to/project  # Uses provided path

# Determine project path
if [ -n "$1" ]; then
    # Use provided path
    PROJECT_PATH="$1"
else
    # Use the directory where the script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_PATH="$SCRIPT_DIR"
fi

# Validate path exists
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Error: Directory does not exist: $PROJECT_PATH"
    exit 1
fi

# Navigate to the project directory
cd "$PROJECT_PATH" || { echo "❌ Error: Cannot access $PROJECT_PATH"; exit 1; }

# Extract project name from directory
PROJECT_NAME=$(basename "$PROJECT_PATH")

echo "============================================"
echo "Setting up workspace for: $PROJECT_PATH"
echo "Project name: $PROJECT_NAME"
echo "============================================"
echo ""

# Create workspace file
echo "Creating workspace file..."
cat > "${PROJECT_NAME}.code-workspace" << 'WORKSPACE_EOF'
{
    "folders": [
        {
            "path": "."
        }
    ]
}
WORKSPACE_EOF

# Create .copilotignore file
echo "Creating .copilotignore file..."
cat > .copilotignore << 'COPILOT_EOF'
# ============================================
# COPILOT IGNORE - PERFORMANCE OPTIMIZATION
# ============================================
# This file tells Copilot which files to NEVER index or touch
# Prevents hanging, slowness, and unauthorized file recreation

# ============================================
# CRITICAL: SQL & MARKDOWN DOCUMENTATION
# ============================================
# NEVER index or recreate these files
*.sql
*.md
**/*.sql
**/*.md

# ============================================
# VIRTUAL ENVIRONMENTS (HUGE - CAUSES HANGS)
# ============================================
branding_gate_VENV/
mubarmij_site_VENV/
**/venv/
**/.venv/
**/env/
**/ENV/
**/__pycache__/

# ============================================
# PYTHON COMPILED & CACHE FILES
# ============================================
__pycache__/
*.py[cod]
*$py.class
*.so
*.pyc
*.pyo
*.pyd
.Python

# ============================================
# STATIC ASSETS (TOO LARGE FOR CONTEXT)
# ============================================
static/selectize.js-master/
static/js/vendor/
static/css/vendor/
static/DataTables/
static/fullcalendar-3.9.0/

# ============================================
# UPLOADS AND USER DATA
# ============================================
uploads/
**/uploads/**

# ============================================
# NODE MODULES (IF ANY)
# ============================================
node_modules/
**/node_modules/**

# ============================================
# BUILD OUTPUTS
# ============================================
dist/
build/
*.egg-info/

# ============================================
# IDE AND EDITOR FILES
# ============================================
.idea/
*.swp
*.swo
*~

# ============================================
# LOG FILES
# ============================================
*.log
logs/

# ============================================
# DATABASE FILES
# ============================================
*.db
*.sqlite
*.sqlite3

# ============================================
# TEMPORARY FILES
# ============================================
tmp/
temp/
*.tmp
COPILOT_EOF

echo "✅ Workspace setup complete!"
echo ""
echo "Files created in: $PROJECT_PATH"
echo "  - ${PROJECT_NAME}.code-workspace"
echo "  - .copilotignore"
echo ""
echo "To open the project in VS Code, run:"
echo "  code \"$PROJECT_PATH/${PROJECT_NAME}.code-workspace\""
echo ""
echo "Or navigate to the project and run:"
echo "  cd \"$PROJECT_PATH\" && code ."
