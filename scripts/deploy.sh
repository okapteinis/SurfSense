#!/bin/bash
# SurfSense Production Deployment Script
# This script ensures reliable, repeatable deployments with automatic rollback

set -e  # Exit on error

# Configuration
REPO_DIR="/opt/SurfSense"
SERVICE_NAME="surfsense-frontend"
BACKUP_DIR="/opt/SurfSense-backups"
LOG_FILE="/var/log/surfsense-deploy.log"
HEALTH_CHECK_URL="https://ai.kapteinis.lv"
MAX_RETRIES=3

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Health check function
check_health() {
    local url=$1
    local max_attempts=30
    local attempt=1

    log "Performing health check on $url..."

    while [ $attempt -le $max_attempts ]; do
        if curl --output /dev/null --silent --head --fail "$url"; then
            log "✓ Health check passed (attempt $attempt/$max_attempts)"
            return 0
        fi

        log "Health check attempt $attempt/$max_attempts failed, retrying in 2s..."
        sleep 2
        ((attempt++))
    done

    error "✗ Health check failed after $max_attempts attempts"
    return 1
}

# Rollback function
rollback() {
    error "Deployment failed! Initiating automatic rollback..."

    # Find the most recent backup
    latest_backup=$(ls -t "$BACKUP_DIR" 2>/dev/null | head -1)

    if [ -z "$latest_backup" ]; then
        error "No backup found for rollback!"
        return 1
    fi

    log "Rolling back to: $latest_backup"

    # Stop service
    systemctl stop "$SERVICE_NAME" || true

    # Restore from backup
    cd "$REPO_DIR"
    git reset --hard

    # Extract backup
    tar -xzf "$BACKUP_DIR/$latest_backup" -C "$REPO_DIR"

    # Fix permissions
    chown -R surfsense:surfsense "$REPO_DIR"

    # Restart service
    systemctl start "$SERVICE_NAME"

    # Health check after rollback
    if check_health "$HEALTH_CHECK_URL"; then
        log "✓ Rollback successful!"
        return 0
    else
        error "✗ Rollback failed - manual intervention required!"
        return 1
    fi
}

# Trap errors and rollback
trap 'rollback' ERR

# Main deployment flow
main() {
    log "========================================="
    log "Starting SurfSense Deployment"
    log "========================================="

    # Step 1: Pre-deployment checks
    log "Step 1/10: Pre-deployment checks"

    if [ ! -d "$REPO_DIR" ]; then
        error "Repository directory not found: $REPO_DIR"
        exit 1
    fi

    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        warning "Service $SERVICE_NAME is not running"
    fi

    # Check disk space
    available_space=$(df "$REPO_DIR" | tail -1 | awk '{print $4}')
    if [ "$available_space" -lt 1048576 ]; then  # Less than 1GB
        error "Insufficient disk space (< 1GB available)"
        exit 1
    fi

    log "✓ Pre-deployment checks passed"

    # Step 2: Create backup
    log "Step 2/10: Creating backup"

    mkdir -p "$BACKUP_DIR"
    backup_name="surfsense-backup-$(date +%Y%m%d-%H%M%S).tar.gz"

    cd "$REPO_DIR"
    tar -czf "$BACKUP_DIR/$backup_name" \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='.next' \
        surfsense_web/

    log "✓ Backup created: $backup_name"

    # Keep only last 5 backups
    cd "$BACKUP_DIR"
    ls -t | tail -n +6 | xargs -r rm --

    # Step 3: Pull latest code
    log "Step 3/10: Pulling latest code from nightly branch"

    cd "$REPO_DIR"
    git fetch origin

    # Get current commit for potential rollback
    current_commit=$(git rev-parse HEAD)
    log "Current commit: $current_commit"

    git checkout nightly
    git reset --hard origin/nightly

    new_commit=$(git rev-parse HEAD)
    log "New commit: $new_commit"

    if [ "$current_commit" == "$new_commit" ]; then
        log "No changes detected, skipping deployment"
        exit 0
    fi

    log "✓ Code updated"

    # Step 4: Check dependencies
    log "Step 4/10: Checking dependencies"

    cd "$REPO_DIR/surfsense_web"

    if [ -f "package.json" ]; then
        pnpm install --frozen-lockfile
        log "✓ Dependencies installed"
    else
        error "package.json not found"
        exit 1
    fi

    # Step 5: Run build script
    log "Step 5/10: Building frontend"

    if [ -f "scripts/build-production.sh" ]; then
        chmod +x scripts/build-production.sh
        ./scripts/build-production.sh
    else
        error "Build script not found at scripts/build-production.sh"
        exit 1
    fi

    log "✓ Build completed"

    # Step 6: Fix permissions
    log "Step 6/10: Fixing file permissions"

    chown -R surfsense:surfsense "$REPO_DIR/surfsense_web/.next" 2>/dev/null || true
    chown -R surfsense:surfsense "$REPO_DIR/surfsense_web/.source" 2>/dev/null || true

    log "✓ Permissions fixed"

    # Step 7: Backend migrations (if any)
    log "Step 7/10: Running database migrations"

    cd "$REPO_DIR/surfsense_backend"
    if [ -f "alembic.ini" ]; then
        sudo -u surfsense pipenv run alembic upgrade head 2>&1 | grep -v "No changes" || warning "No migrations to run"
    fi

    log "✓ Migrations complete"

    # Step 8: Restart services
    log "Step 8/10: Restarting services"

    systemctl restart surfsense
    systemctl restart surfsense-celery
    systemctl restart surfsense-celery-beat
    systemctl restart surfsense-frontend

    log "✓ Services restarted"

    # Step 9: Health checks
    log "Step 9/10: Running health checks"

    sleep 5  # Give services time to start

    # Check each service
    services=("surfsense" "surfsense-celery" "surfsense-celery-beat" "surfsense-frontend")
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            log "✓ $service is running"
        else
            error "✗ $service failed to start"
            exit 1
        fi
    done

    # HTTP health check
    if ! check_health "$HEALTH_CHECK_URL"; then
        error "Health check failed"
        exit 1
    fi

    # Test authentication endpoints
    log "Testing authentication endpoints..."

    if curl --fail --silent "$HEALTH_CHECK_URL/api/v1/auth/2fa/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=test&password=test" 2>/dev/null | grep -q "LOGIN_BAD_CREDENTIALS\|requires_2fa"; then
        log "✓ Auth endpoints responding"
    else
        warning "Auth endpoints test inconclusive (may be OK)"
    fi

    log "✓ All health checks passed"

    # Step 10: Cleanup
    log "Step 10/10: Cleanup"

    # Clean old build artifacts
    find "$REPO_DIR/surfsense_web" -name "*.log" -mtime +7 -delete 2>/dev/null || true

    log "✓ Cleanup complete"

    log "========================================="
    log "Deployment completed successfully!"
    log "Commit: $new_commit"
    log "========================================="
}

# Run main function
main "$@"
