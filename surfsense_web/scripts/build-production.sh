#!/bin/bash
# Production build script that handles fumadocs issues

set -e  # Exit on error

echo "=== Starting production build ==="

# Save original locations
DOCS_BACKUP="/tmp/surfsense_docs_backup"
SEARCH_BACKUP="/tmp/surfsense_search_backup"

# Move problematic routes out of app directory
if [ -d "app/docs" ]; then
    echo "Moving docs directory to temporary location..."
    mv app/docs "$DOCS_BACKUP"
fi

if [ -d "app/api/search" ]; then
    echo "Moving search API to temporary location..."
    mv app/api/search "$SEARCH_BACKUP"
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf .next

# Run build
echo "Running pnpm build..."
pnpm build

# Restore routes
if [ -d "$DOCS_BACKUP" ]; then
    echo "Restoring docs directory..."
    mv "$DOCS_BACKUP" app/docs
fi

if [ -d "$SEARCH_BACKUP" ]; then
    echo "Restoring search API..."
    mv "$SEARCH_BACKUP" app/api/search
fi

# Fix permissions if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Fixing file permissions..."
    chown -R surfsense:surfsense .next .source
fi

echo "=== Build completed successfully ==="
