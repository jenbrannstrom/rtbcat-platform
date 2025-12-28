#!/bin/bash

# Phase 8.2 Documentation Setup Script
# Copies documentation from /mnt/user-data/outputs/ to repository

set -e  # Exit on error

echo "🚀 Phase 8.2 Documentation Setup"
echo "================================"
echo ""

# Define paths
REPO_PATH="$HOME/Documents/rtbcat-platform"
DOCS_PATH="$REPO_PATH/docs/phases/phase-8.2"
SOURCE_PATH="/mnt/user-data/outputs"

# Check if repo exists
if [ ! -d "$REPO_PATH" ]; then
    echo "❌ Repository not found at: $REPO_PATH"
    echo "Please update REPO_PATH in this script to match your setup."
    exit 1
fi

echo "✅ Repository found: $REPO_PATH"
echo ""

# Create documentation directory
echo "📁 Creating documentation directory..."
mkdir -p "$DOCS_PATH"
echo "✅ Created: $DOCS_PATH"
echo ""

# Copy files
echo "📄 Copying documentation files..."

# 1. README (master summary)
cp "$SOURCE_PATH/PHASE_8.2_README.md" "$DOCS_PATH/README.md"
echo "  ✅ README.md"

# 2. Preflight checklist
cp "$SOURCE_PATH/PHASE_8.2_PREFLIGHT.md" "$DOCS_PATH/01-PREFLIGHT.md"
echo "  ✅ 01-PREFLIGHT.md"

# 3. Requirements/Prompt
cp "$SOURCE_PATH/PHASE_8.2_PROMPT.md" "$DOCS_PATH/02-REQUIREMENTS.md"
echo "  ✅ 02-REQUIREMENTS.md"

# 4. Code examples
cp "$SOURCE_PATH/PHASE_8.2_CODE_EXAMPLES.md" "$DOCS_PATH/03-CODE-EXAMPLES.md"
echo "  ✅ 03-CODE-EXAMPLES.md"

# 5. Quick reference
cp "$SOURCE_PATH/PHASE_8.2_QUICK_REFERENCE.md" "$DOCS_PATH/04-QUICK-REFERENCE.md"
echo "  ✅ 04-QUICK-REFERENCE.md"

# 6. Workflow diagram
cp "$SOURCE_PATH/PHASE_8.2_WORKFLOW.md" "$DOCS_PATH/05-WORKFLOW.md"
echo "  ✅ 05-WORKFLOW.md"

# 7. Index
cp "$SOURCE_PATH/PHASE_8.2_INDEX.md" "$DOCS_PATH/INDEX.md"
echo "  ✅ INDEX.md"

echo ""
echo "📊 Summary"
echo "=========="
ls -lh "$DOCS_PATH" | tail -n +2

echo ""
echo "✨ Documentation successfully saved!"
echo ""
echo "📍 Location: $DOCS_PATH"
echo ""
echo "🎯 Quick Access Commands:"
echo "  cd $REPO_PATH"
echo "  cat docs/phases/phase-8.2/README.md"
echo "  ls docs/phases/phase-8.2/"
echo ""
echo "🤖 For Claude CLI:"
echo "  'Please read docs/phases/phase-8.2/README.md to understand Phase 8.2'"
echo ""
echo "💾 Next Steps:"
echo "  1. Review the documentation: cat docs/phases/phase-8.2/README.md"
echo "  2. Commit to git: git add docs/phases/phase-8.2 && git commit -m 'docs: Add Phase 8.2 documentation'"
echo "  3. Start development: Follow 01-PREFLIGHT.md checklist"
echo ""
echo "✅ Setup complete! Ready for Phase 8.2 development."
