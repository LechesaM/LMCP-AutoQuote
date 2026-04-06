#!/bin/bash

set -u

PROJECT_ROOT="/Users/Shared/LMCP-AutoQuote-Server"
RUNTIME_DIR="$PROJECT_ROOT/runtime"
PAUSE_FLAG="$RUNTIME_DIR/harvester.paused"
LOG_FILE="$PROJECT_ROOT/clean_health_check.log"

CRITICAL_GB=10
WARNING_GB=20

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  echo "[$(timestamp)] $1" | tee -a "$LOG_FILE"
}

section() {
  echo ""
  echo "=================================================="
  echo "$1"
  echo "=================================================="
}

free_gb_root() {
  df -k / | awk 'NR==2 {printf "%.2f", $4/1024/1024}'
}

free_gb_project_disk() {
  df -k "$PROJECT_ROOT" 2>/dev/null | awk 'NR==2 {printf "%.2f", $4/1024/1024}'
}

ensure_runtime_dir() {
  mkdir -p "$RUNTIME_DIR"
}

pause_harvester_if_low_disk() {
  ensure_runtime_dir
  local free_gb
  free_gb=$(free_gb_root | cut -d. -f1)

  if [ "$free_gb" -lt "$CRITICAL_GB" ]; then
    touch "$PAUSE_FLAG"
    log "CRITICAL: Free disk below ${CRITICAL_GB}GB. Harvester pause flag created at $PAUSE_FLAG"
  else
    if [ -f "$PAUSE_FLAG" ]; then
      rm -f "$PAUSE_FLAG"
      log "Disk recovered above critical threshold. Removed pause flag."
    fi
  fi
}

safe_rm_contents() {
  local target="$1"
  if [ -d "$target" ]; then
    rm -rf "${target:?}/"* 2>/dev/null || true
  fi
}

safe_sudo_rm_contents() {
  local target="$1"
  if [ -d "$target" ]; then
    sudo rm -rf "${target:?}/"* 2>/dev/null || true
  fi
}

cleanup_macos_user_space() {
  section "CLEANING USER-LEVEL MACOS SPACE"

  log "Cleaning user caches..."
  safe_rm_contents "$HOME/Library/Caches"

  log "Cleaning user logs..."
  safe_rm_contents "$HOME/Library/Logs"

  log "Cleaning Mail downloads..."
  safe_rm_contents "$HOME/Library/Containers/com.apple.mail/Data/Library/Mail Downloads"

  log "Cleaning CrashReporter files..."
  safe_rm_contents "$HOME/Library/Application Support/CrashReporter"

  log "Cleaning VS Code cache..."
  safe_rm_contents "$HOME/Library/Application Support/Code/Cache"

  log "Cleaning pip cache..."
  if command -v pip3 >/dev/null 2>&1; then
    pip3 cache purge >/dev/null 2>&1 || true
  elif command -v pip >/dev/null 2>&1; then
    pip cache purge >/dev/null 2>&1 || true
  fi

  log "Cleaning Xcode DerivedData..."
  rm -rf "$HOME/Library/Developer/Xcode/DerivedData"/* 2>/dev/null || true

  log "Removing Previously Relocated Items..."
  rm -rf /Users/Shared/Previously\ Relocated\ Items* 2>/dev/null || true

  log "Running Homebrew cleanup if available..."
  if command -v brew >/dev/null 2>&1; then
    brew cleanup >/dev/null 2>&1 || true
  fi
}

cleanup_macos_system_space() {
  section "CLEANING SYSTEM-LEVEL MACOS SPACE"

  if sudo -n true 2>/dev/null; then
    log "Cleaning /private/var/log ..."
    safe_sudo_rm_contents "/private/var/log"

    log "Cleaning /private/var/tmp ..."
    safe_sudo_rm_contents "/private/var/tmp"

    log "Attempting Time Machine local snapshot cleanup..."
    if command -v tmutil >/dev/null 2>&1; then
      mapfile -t snapshots < <(tmutil listlocalsnapshots / 2>/dev/null | awk -F. '/com.apple.TimeMachine/ {print $4}')
      for snap in "${snapshots[@]}"; do
        [ -n "$snap" ] && sudo tmutil deletelocalsnapshots "$snap" >/dev/null 2>&1 || true
      done
    fi
  else
    log "Skipping sudo-only cleanup because sudo access is not active."
    log "Run 'sudo -v' first, then run the script again for deeper cleanup."
  fi
}

docker_cli_exists() {
  command -v docker >/dev/null 2>&1
}

docker_daemon_up() {
  docker info >/dev/null 2>&1
}

start_docker_desktop() {
  section "STARTING DOCKER DESKTOP"
  if ! docker_cli_exists; then
    log "Docker CLI not found."
    return
  fi

  if docker_daemon_up; then
    log "Docker daemon already running."
    return
  fi

  log "Attempting to open Docker Desktop..."
  open -a Docker >/dev/null 2>&1 || true

  local i=0
  while [ $i -lt 24 ]; do
    if docker_daemon_up; then
      log "Docker daemon is now running."
      return
    fi
    sleep 5
    i=$((i+1))
    log "Waiting for Docker daemon... attempt $i/24"
  done

  log "Docker did not come up within the wait window."
}

cleanup_docker() {
  section "CLEANING DOCKER SPACE"

  if ! docker_cli_exists; then
    log "Docker CLI not installed."
    return
  fi

  if ! docker_daemon_up; then
    log "Docker daemon is still down. Skipping Docker cleanup."
    return
  fi

  log "Docker disk usage before cleanup:"
  docker system df 2>/dev/null | tee -a "$LOG_FILE" || true

  log "Pruning stopped containers, unused networks, dangling images..."
  docker system prune -f >/dev/null 2>&1 || true

  log "Pruning builder cache..."
  docker builder prune -af >/dev/null 2>&1 || true

  log "Pruning unused images..."
  docker image prune -af >/dev/null 2>&1 || true

  log "Pruning unused volumes..."
  docker volume prune -f >/dev/null 2>&1 || true

  log "Docker disk usage after cleanup:"
  docker system df 2>/dev/null | tee -a "$LOG_FILE" || true
}

project_health_check() {
  section "LMCP PROJECT HEALTH CHECK"

  if [ -d "$PROJECT_ROOT" ]; then
    log "Project root exists: $PROJECT_ROOT"
  else
    log "ERROR: Project root not found: $PROJECT_ROOT"
    return
  fi

  if [ -f "$PROJECT_ROOT/.env" ]; then
    log ".env file found."
  else
    log "WARNING: .env file not found."
  fi

  if [ -d "$PROJECT_ROOT/app" ]; then
    log "app directory found."
  else
    log "WARNING: app directory not found."
  fi

  if [ -f "$PROJECT_ROOT/app/main.py" ]; then
    log "app/main.py found."
  else
    log "WARNING: app/main.py not found."
  fi

  if [ -d "$PROJECT_ROOT/monthly_quotes" ]; then
    log "monthly_quotes directory found."
  else
    log "WARNING: monthly_quotes directory not found."
  fi

  if command -v python3 >/dev/null 2>&1; then
    log "Python version: $(python3 --version 2>&1)"
  else
    log "WARNING: python3 not found."
  fi

  if command -v curl >/dev/null 2>&1; then
    log "Checking FastAPI health endpoints..."
    curl -fsS http://127.0.0.1:8000/docs >/dev/null 2>&1 \
      && log "Swagger docs reachable at http://127.0.0.1:8000/docs" \
      || log "Swagger docs not reachable."

    curl -fsS http://127.0.0.1:8000/dashboard/system-health >/dev/null 2>&1 \
      && log "/dashboard/system-health reachable." \
      || log "/dashboard/system-health not reachable."

    curl -fsS http://127.0.0.1:8000/autonomous/status >/dev/null 2>&1 \
      && log "/autonomous/status reachable." \
      || log "/autonomous/status not reachable."
  else
    log "curl not found. Skipping HTTP checks."
  fi
}

show_space_report() {
  section "SPACE REPORT"

  log "Root disk free GB: $(free_gb_root)"
  log "Project disk free GB: $(free_gb_project_disk)"

  echo ""
  echo "Top space usage in /Users/Shared:"
  du -h -d 1 /Users/Shared 2>/dev/null | sort -h | tail -20

  echo ""
  echo "Top space usage in your Library:"
  du -h -d 1 "$HOME/Library" 2>/dev/null | sort -h | tail -20
}

docker_container_status() {
  section "DOCKER CONTAINER STATUS"

  if docker_daemon_up; then
    docker ps -a 2>/dev/null || true
  else
    log "Docker daemon unavailable. Cannot list containers."
  fi
}

final_summary() {
  section "FINAL SUMMARY"

  local free_gb_raw
  free_gb_raw=$(free_gb_root)
  local free_gb_int
  free_gb_int=$(echo "$free_gb_raw" | cut -d. -f1)

  log "Final free disk: ${free_gb_raw} GB"

  if [ "$free_gb_int" -lt "$CRITICAL_GB" ]; then
    log "STATUS: CRITICAL — still below ${CRITICAL_GB}GB free."
  elif [ "$free_gb_int" -lt "$WARNING_GB" ]; then
    log "STATUS: WARNING — below ${WARNING_GB}GB free."
  else
    log "STATUS: HEALTHY — above ${WARNING_GB}GB free."
  fi

  if docker_daemon_up; then
    log "Docker status: RUNNING"
  else
    log "Docker status: DOWN"
  fi

  log "Detailed log saved to: $LOG_FILE"
}

main() {
  : > "$LOG_FILE"
  section "LMCP CLEAN + HEALTH CHECK"
  log "Starting emergency cleanup and health check..."

  pause_harvester_if_low_disk
  show_space_report
  cleanup_macos_user_space
  cleanup_macos_system_space
  show_space_report
  start_docker_desktop
  cleanup_docker
  docker_container_status
  pause_harvester_if_low_disk
  project_health_check
  final_summary
}

main
