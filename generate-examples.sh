#!/usr/bin/env bash

#
# Script to generate all plugin examples
# This provides a consistent set of examples for documentation purposes
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="${SCRIPT_DIR}/examples"
BOOTSTRAP_CMD="${SCRIPT_DIR}/run.sh"

echo "=========================================="
echo "Rundeck Plugin Bootstrap - Example Generator"
echo "=========================================="
echo ""

# Clean examples directory if it exists
if [ -d "$EXAMPLES_DIR" ]; then
    echo "Cleaning existing examples directory..."
    rm -rf "$EXAMPLES_DIR"
fi

mkdir -p "$EXAMPLES_DIR"

# Build the bootstrap tool first
echo "Building rundeck-plugin-bootstrap..."
./gradlew clean build shadowDistZip > /dev/null 2>&1
echo "✓ Build complete"
echo ""

# Extract the shadow distribution
cd build/distributions
SHADOW_ZIP=$(ls rundeck-plugin-bootstrap-shadow-*.zip | head -1)
unzip -q "$SHADOW_ZIP"
SHADOW_DIR=$(basename "$SHADOW_ZIP" .zip)
cd "$SCRIPT_DIR"

BOOTSTRAP_BIN="./build/distributions/${SHADOW_DIR}/bin/rundeck-plugin-bootstrap"

echo "Generating example plugins..."
echo ""

# Java Plugin Examples
echo "Java Plugins:"
echo "  → Notification Plugin"
$BOOTSTRAP_BIN -n "Example Notification" -t java -s Notification -d "$EXAMPLES_DIR/java-plugins"

echo "  → Workflow Step Plugin"
$BOOTSTRAP_BIN -n "Example Workflow Step" -t java -s WorkflowStep -d "$EXAMPLES_DIR/java-plugins"

echo "  → Workflow Node Step Plugin"
$BOOTSTRAP_BIN -n "Example Workflow Node Step" -t java -s WorkflowNodeStep -d "$EXAMPLES_DIR/java-plugins"

echo "  → Resource Model Source Plugin"
$BOOTSTRAP_BIN -n "Example Resource Model Source" -t java -s ResourceModelSource -d "$EXAMPLES_DIR/java-plugins"

echo "  → Log Filter Plugin"
$BOOTSTRAP_BIN -n "Example Log Filter" -t java -s LogFilter -d "$EXAMPLES_DIR/java-plugins"

echo "  → Node Executor Plugin"
$BOOTSTRAP_BIN -n "Example Node Executor" -t java -s NodeExecutor -d "$EXAMPLES_DIR/java-plugins"

echo "  → Orchestrator Plugin"
$BOOTSTRAP_BIN -n "Example Orchestrator" -t java -s Orchestrator -d "$EXAMPLES_DIR/java-plugins"

echo "  → Option Plugin"
$BOOTSTRAP_BIN -n "Example Option" -t java -s Option -d "$EXAMPLES_DIR/java-plugins"

echo ""

# Script Plugin Examples
echo "Script Plugins:"
echo "  → Node Executor Plugin"
$BOOTSTRAP_BIN -n "Example Script Node Executor" -t script -s NodeExecutor -d "$EXAMPLES_DIR/script-plugins"

echo "  → Workflow Node Step Plugin"
$BOOTSTRAP_BIN -n "Example Script Workflow Step" -t script -s WorkflowNodeStep -d "$EXAMPLES_DIR/script-plugins"

echo "  → Resource Model Source Plugin"
$BOOTSTRAP_BIN -n "Example Script Resource Model" -t script -s ResourceModelSource -d "$EXAMPLES_DIR/script-plugins"

echo "  → File Copier Plugin"
$BOOTSTRAP_BIN -n "Example Script File Copier" -t script -s FileCopier -d "$EXAMPLES_DIR/script-plugins"

echo "  → Option Plugin"
$BOOTSTRAP_BIN -n "Example Script Option" -t script -s Option -d "$EXAMPLES_DIR/script-plugins"

echo ""

# UI Plugin Examples
echo "UI Plugins:"
echo "  → UI Plugin"
$BOOTSTRAP_BIN -n "Example UI Plugin" -t ui -s UI -d "$EXAMPLES_DIR/ui-plugins"

echo ""
echo "=========================================="
echo "✓ All examples generated successfully!"
echo "=========================================="
echo ""
echo "Examples are located in: $EXAMPLES_DIR"
echo ""
echo "Directory structure:"
tree -L 2 "$EXAMPLES_DIR" 2>/dev/null || find "$EXAMPLES_DIR" -maxdepth 2 -type d | sed 's|[^/]*/| |g'
echo ""
