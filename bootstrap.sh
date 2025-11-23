#!/usr/bin/env bash
# Bootstrap script for one-command TGO deployment
# Usage (remote):  curl -fsSL https://your.host/bootstrap.sh | bash
# Usage (local):   bash bootstrap.sh

set -euo pipefail

# ---------- Configuration (overridable via env) ----------
REPO="${REPO:-https://github.com/tgoai/tgo.git}"
DIR="${DIR:-tgo}"
REF="${REF:-}"

# ---------- Notifications ----------
notify() {
  if command -v afplay >/dev/null 2>&1 && [ "$(uname)" = "Darwin" ]; then
    afplay /System/Library/Sounds/Glass.aiff || true
  else
    printf '\a' || true
  fi
}

_finish() {
  local code=$?
  if [ $code -eq 0 ]; then
    printf '\n[OK] Bootstrap completed.\n'
  else
    printf '\n[ERROR] Bootstrap failed with code %s\n' "$code"
  fi
  notify
  exit $code
}
trap _finish EXIT

# ---------- Pre-flight checks ----------

OS_TYPE="unknown"
OS_DISTRO="unknown"
OS_IS_WSL=0
DOCKER_GROUP_JUST_ADDED=0


detect_os() {
  case "$(uname -s)" in
    Darwin)
      OS_TYPE="macos"
      ;;
    Linux)
      OS_TYPE="linux"
      if grep -qi "microsoft" /proc/version 2>/dev/null || \
         grep -qi "WSL" /proc/sys/kernel/osrelease 2>/dev/null; then
        OS_IS_WSL=1
      fi
      if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "${ID:-}" in
          ubuntu|debian)
            OS_DISTRO="debian"
            ;;
          centos|rhel)
            OS_DISTRO="rhel"
            ;;
          fedora)
            OS_DISTRO="fedora"
            ;;
          arch)
            OS_DISTRO="arch"
            ;;
          *)
            OS_DISTRO="${ID:-unknown}"
            ;;
        esac
      fi
      ;;
    *)
      OS_TYPE="unknown"
      OS_DISTRO="unknown"
      ;;
  esac
}

confirm() {
  local prompt="$1"
  local answer=""

  # Print prompt and read from real TTY when possible so that
  #   - running via "curl ... | bash" still works interactively
  #   - leftover stdin data does not auto-answer the question
  printf "%s " "$prompt"

  if [ -r /dev/tty ]; then
    if ! read -r answer < /dev/tty; then
      echo "[FATAL] Unable to read user input from /dev/tty. Please run this script from an interactive shell." >&2
      exit 1
    fi
  else
    if ! read -r answer; then
      echo "[FATAL] Unable to read user input. Please run this script from an interactive shell." >&2
      exit 1
    fi
  fi

  # Normalize answer: strip a single trailing CR in case of odd TTY settings
  answer=${answer%$'\r'}

  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *)          return 1 ;;
  esac
}


install_git() {
  detect_os
  if ! confirm "Git is not installed. Would you like to install it now? [y/N]"; then
    echo "[FATAL] Git is required. Please install Git and re-run this script." >&2
    exit 1
  fi

  if [ "$OS_TYPE" = "macos" ]; then
    if command -v brew >/dev/null 2>&1; then
      echo "[INFO] Installing Git via Homebrew..."
      set +e
      brew install git
      status=$?
      set -e
      if [ $status -ne 0 ]; then
        echo "[FATAL] Failed to install Git via Homebrew. Please install it manually." >&2
        echo "        https://git-scm.com/downloads" >&2
        exit 1
      fi
    else
      echo "[INFO] Running 'xcode-select --install' to install Apple Command Line Tools (includes Git)..." >&2
      set +e
      xcode-select --install
      status=$?
      set -e
      if [ $status -ne 0 ]; then
        echo "[WARN] 'xcode-select --install' did not complete successfully." >&2
      fi
      # Even if the command returns non-zero, Git may already be available if CLT were installed before.
      if ! command -v git >/dev/null 2>&1; then
        echo "[FATAL] Git is still not available. Please install Git manually for macOS:" >&2
        echo "        https://git-scm.com/download/mac" >&2
        exit 1
      fi
      echo "[INFO] Apple Command Line Tools installation appears complete."
    fi
  elif [ "$OS_TYPE" = "linux" ]; then
    if ! command -v sudo >/dev/null 2>&1; then
      echo "[FATAL] sudo is not available. Please ask your system administrator to install Git." >&2
      exit 1
    fi
    echo "[INFO] Installing Git using the system package manager..."
    set +e
    case "$OS_DISTRO" in
      debian)
        sudo apt-get update && sudo apt-get install -y git
        ;;
      rhel|fedora)
        if command -v dnf >/dev/null 2>&1; then
          sudo dnf install -y git
        else
          sudo yum install -y git
        fi
        ;;
      arch)
        sudo pacman -Sy --noconfirm git
        ;;
      *)
        echo "[WARN] Unsupported or unknown Linux distribution ($OS_DISTRO)." >&2
        echo "       Please install Git manually: https://git-scm.com/download/linux" >&2
        set -e
        exit 1
        ;;
    esac
    status=$?
    set -e
    if [ $status -ne 0 ]; then
      echo "[FATAL] Automatic Git installation failed. Please install Git manually." >&2
      echo "        https://git-scm.com/downloads" >&2
      exit 1
    fi
  else
    echo "[FATAL] Unsupported OS. Please install Git manually: https://git-scm.com/downloads" >&2
    exit 1
  fi

  if ! command -v git >/dev/null 2>&1; then
    echo "[FATAL] Git installation did not succeed. Please install it manually." >&2
    exit 1
  fi

  echo "[INFO] Git installation looks OK: $(git --version 2>/dev/null || echo 'version check failed')"
}
install_docker_linux_debian() {
  echo "[INFO] Using apt-based installation (Debian/Ubuntu)..."
  sudo apt-get update
  sudo apt-get remove -y docker docker-engine docker.io containerd runc || true
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  if [ -f /etc/os-release ]; then
    . /etc/os-release
  fi
  curl -fsSL "https://download.docker.com/linux/${ID:-debian}/gpg" | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  arch_dpkg="$(dpkg --print-architecture)"
  echo "deb [arch=${arch_dpkg} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${ID:-debian} ${VERSION_CODENAME:-stable} stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_docker_linux_rhel() {
  echo "[INFO] Using yum-based installation (RHEL/CentOS)..."
  sudo yum remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine || true
  sudo yum install -y yum-utils
  sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_docker_linux_fedora() {
  echo "[INFO] Using dnf-based installation (Fedora)..."
  sudo dnf remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine || true
  sudo dnf -y install dnf-plugins-core
  sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_docker_linux_arch() {
  echo "[INFO] Using pacman-based installation (Arch Linux)..."
  sudo pacman -Sy --noconfirm docker docker-compose
}



install_docker() {
  detect_os
  if ! confirm "Docker is not installed. Would you like to install it now? [y/N]"; then
    echo "[FATAL] Docker is required. Please install Docker and re-run this script." >&2
    echo "        https://docs.docker.com/get-docker/" >&2
    exit 1
  fi

  if [ "$OS_TYPE" = "macos" ]; then
    echo "[INFO] Detecting system architecture..."
    arch="$(uname -m)"
    case "$arch" in
      arm64) docker_arch="arm64" ;;
      x86_64) docker_arch="amd64" ;;
      *) docker_arch="amd64" ;;
    esac

    DOWNLOAD_URL="https://desktop.docker.com/mac/main/${docker_arch}/Docker.dmg"
    DOWNLOAD_PATH="${TMPDIR:-/tmp}/Docker.dmg"

    echo "[INFO] Downloading Docker Desktop for Mac ($arch) from $DOWNLOAD_URL ..."
    if command -v curl >/dev/null 2>&1; then
      set +e
      curl -L "$DOWNLOAD_URL" -o "$DOWNLOAD_PATH"
      status=$?
      set -e
    else
      status=1
    fi

    if [ $status -ne 0 ]; then
      echo "[WARN] Automatic download of Docker Desktop failed."
      if command -v open >/dev/null 2>&1; then
        echo "[INFO] Opening Docker Desktop installation page in your browser..."
        open "https://docs.docker.com/desktop/setup/install/mac-install/" || true
      fi
      echo "[FATAL] Please download and install Docker Desktop manually, then re-run this script." >&2
      exit 1
    fi

    echo "[INFO] Attaching Docker Desktop disk image..."
    set +e
    sudo hdiutil attach "$DOWNLOAD_PATH"
    attach_status=$?
    if [ $attach_status -eq 0 ]; then
      echo "[INFO] Running Docker Desktop installer (this may take several minutes)..."
      sudo /Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license
      install_status=$?
      echo "[INFO] Detaching Docker Desktop disk image..."
      sudo hdiutil detach /Volumes/Docker || true
    else
      install_status=1
    fi
    set -e

    if [ ${install_status:-1} -ne 0 ]; then
      echo "[WARN] Automatic Docker Desktop installation may have failed." >&2
      if command -v open >/dev/null 2>&1; then
        echo "[INFO] Opening Docker Desktop installation page in your browser..." >&2
        open "https://docs.docker.com/desktop/setup/install/mac-install/" || true
      fi
      echo "[FATAL] Please complete Docker Desktop installation manually, then re-run this script." >&2
      exit 1
    fi

    echo "[INFO] Docker Desktop installation command completed. You may need to open Docker.app once from /Applications to finish initialization." >&2

  elif [ "$OS_TYPE" = "linux" ]; then
    if [ "$OS_IS_WSL" -eq 1 ]; then
      echo "[WARN] Detected WSL2 environment. The recommended setup is Docker Desktop for Windows with WSL2 integration:" >&2
      echo "       https://docs.docker.com/desktop/wsl/" >&2
    fi

    if ! command -v sudo >/dev/null 2>&1; then
      echo "[FATAL] sudo is not available. Please ask your system administrator to install Docker." >&2
      exit 1
    fi

    # Track whether we are newly adding the current user to the 'docker' group.
    local docker_group_was_present=0
    if command -v id >/dev/null 2>&1; then
      local groups_before=""
      groups_before="$(id -nG "$USER" 2>/dev/null || echo "")"
      case " $groups_before " in
        *" docker "*) docker_group_was_present=1 ;;
      esac
    fi

    echo "[INFO] Installing Docker Engine from official Docker repository..."
    set +e
    case "$OS_DISTRO" in
      debian)
        install_docker_linux_debian
        ;;
      rhel)
        install_docker_linux_rhel
        ;;
      fedora)
        install_docker_linux_fedora
        ;;
      arch)
        install_docker_linux_arch
        ;;
      *)
        echo "[WARN] Unsupported or unknown Linux distribution ($OS_DISTRO)." >&2
        echo "       Please install Docker manually: https://docs.docker.com/engine/install/" >&2
        set -e
        exit 1
        ;;
    esac
    status=$?
    set -e
    if [ $status -ne 0 ]; then
      echo "[FATAL] Automatic Docker installation failed. Please install Docker manually:" >&2
      echo "        https://docs.docker.com/engine/install/" >&2
      exit 1
    fi

    if command -v systemctl >/dev/null 2>&1; then
      echo "[INFO] Starting and enabling Docker service (systemd)..."
      sudo systemctl start docker || true
      sudo systemctl enable docker || true
    fi

    if command -v getent >/dev/null 2>&1 && getent group docker >/dev/null 2>&1; then
      echo "[INFO] Adding current user to 'docker' group (you may need to log out and back in)."
      sudo usermod -aG docker "$USER" || true

      # If the user was not previously in the 'docker' group but is now,
      # remember this so we can avoid running tgo.sh in the same session,
      # which would still lack Docker permissions.
      if command -v id >/dev/null 2>&1; then
        local groups_after=""
        groups_after="$(id -nG "$USER" 2>/dev/null || echo "")"
        case " $groups_after " in
          *" docker "*)
            if [ "$docker_group_was_present" -eq 0 ]; then
              DOCKER_GROUP_JUST_ADDED=1
            fi
            ;;
        esac
      fi
    fi
  else
    echo "[FATAL] Unsupported OS. Please install Docker manually: https://docs.docker.com/get-docker/" >&2
    exit 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "[FATAL] Docker installation did not succeed. Please install it manually." >&2
    exit 1
  fi

  echo "[INFO] Docker installation looks OK: $(docker --version 2>/dev/null || echo 'version check failed')"
}

install_docker_compose() {
  detect_os
  if ! confirm "Docker Compose plugin is not installed. Would you like to install it now? [y/N]"; then
    echo "[FATAL] Docker Compose plugin is required. Please install it and re-run this script." >&2
    echo "        https://docs.docker.com/compose/install/" >&2
    exit 1
  fi

  if [ "$OS_TYPE" = "macos" ]; then
    echo "[INFO] On macOS, 'docker compose' is provided by Docker Desktop." >&2
    if [ -d "/Applications/Docker.app" ] && command -v open >/dev/null 2>&1; then
      echo "[INFO] Opening Docker Desktop so you can check for updates..." >&2
      open -a Docker || true
    fi
    if command -v open >/dev/null 2>&1; then
      echo "[INFO] Opening Docker Desktop installation/upgrade page in your browser..." >&2
      open "https://docs.docker.com/desktop/setup/install/mac-install/" || true
    fi
    echo "[FATAL] Please ensure Docker Desktop is installed and up to date, then re-run this script." >&2
    exit 1
  elif [ "$OS_TYPE" = "linux" ]; then
    if ! command -v sudo >/dev/null 2>&1; then
      echo "[FATAL] sudo is not available. Please ask your system administrator to install Docker Compose plugin." >&2
      exit 1
    fi

    echo "[INFO] Installing Docker Compose plugin using the system package manager..."
    set +e
    case "$OS_DISTRO" in
      debian)
        sudo apt-get update && sudo apt-get install -y docker-compose-plugin
        ;;
      rhel|fedora)
        if command -v dnf >/dev/null 2>&1; then
          sudo dnf install -y docker-compose-plugin
        else
          sudo yum install -y docker-compose-plugin
        fi
        ;;
      arch)
        sudo pacman -Sy --noconfirm docker-compose
        ;;
      *)
        echo "[WARN] Unsupported or unknown Linux distribution ($OS_DISTRO)." >&2
        echo "       Please install Docker Compose manually: https://docs.docker.com/compose/install/" >&2
        set -e
        exit 1
        ;;
    esac
    status=$?
    set -e
    if [ $status -ne 0 ]; then
      echo "[FATAL] Automatic Docker Compose plugin installation failed. Please install it manually:" >&2
      echo "        https://docs.docker.com/compose/install/" >&2
      exit 1
    fi
  else
    echo "[FATAL] Unsupported OS. Please install Docker Compose plugin manually: https://docs.docker.com/compose/install/" >&2
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    echo "[FATAL] Docker Compose plugin installation did not succeed. Please install it manually." >&2
    exit 1
  fi

  echo "[INFO] Docker Compose plugin installation looks OK."
}

check_prereqs() {
  if ! command -v git >/dev/null 2>&1; then
    install_git
  fi

  if ! command -v docker >/dev/null 2>&1; then
    install_docker
  fi

  if ! docker compose version >/dev/null 2>&1; then
    install_docker_compose
  fi
}

# ---------- Image tag helpers ----------
update_image_tags() {
  local image_tag="$1"
  local compose_main="$DIR/docker-compose.yml"
  local compose_cn="$DIR/docker-compose.cn.yml"

  echo "[INFO] Setting Docker image tags to '$image_tag' for TGO application services..."

  if [ -f "$compose_main" ]; then
    echo "[INFO] Updating $compose_main ..."
    sed -i.bak -E "s#(ghcr.io/tgoai/tgo/tgo-[^:]+:)[^[:space:]]+#\1${image_tag}#g" "$compose_main" || {
      echo "[WARN] Failed to update image tags in $compose_main"
    }
  else
    echo "[INFO] $compose_main not found; skipping."
  fi

  if [ -f "$compose_cn" ]; then
    echo "[INFO] Updating $compose_cn ..."
    sed -i.bak -E "s#(registry.cn-shanghai.aliyuncs.com/tgoai/tgo-[^:]+:)[^[:space:]]+#\1${image_tag}#g" "$compose_cn" || {
      echo "[WARN] Failed to update image tags in $compose_cn"
    }
  else
    echo "[INFO] $compose_cn not found; skipping."
  fi
}


# ---------- Main ----------
main() {
  check_prereqs

  # If Docker was just installed and we have just added this user to the
  # 'docker' group on Linux, the current shell will not yet see that group.
  # In that case, instruct the user to start a new session instead of
  # continuing into tgo.sh install, which would hit permission errors.
  detect_os
  if [ "$OS_TYPE" = "linux" ] && [ "${DOCKER_GROUP_JUST_ADDED:-0}" -eq 1 ]; then
    echo "[INFO] Docker Engine was installed and your user was just added to the 'docker' group." >&2
    echo "[INFO] To use Docker without sudo, you must start a new shell session so the new group membership is applied." >&2
    echo >&2
    echo "Next steps (choose one):" >&2
    echo "  1) Log out and log back in, then run (from your tgo-deploy repo directory):" >&2
    echo "       ./tgo.sh install" >&2
    echo "     OR" >&2
    echo "  2) In this terminal, run:" >&2
    echo "       newgrp docker" >&2
    echo "       ./tgo.sh install" >&2
    echo >&2
    echo "[INFO] Exiting bootstrap now so you can restart your session with Docker permissions." >&2
    return
  fi

  # If we're already inside a tgo-deploy working dir, run tgo.sh install
  if [ -f "./tgo.sh" ] && [ -f "./docker-compose.yml" ]; then
    echo "[INFO] Detected existing tgo-deploy checkout in $(pwd). Running ./tgo.sh install..."
    ./tgo.sh install
    return
  fi


  # Otherwise, clone the repo to DIR and run tgo.sh install
  if [ -d "$DIR/.git" ]; then
    echo "[OK] Repository already present: $DIR"
  else
    echo "[CLONE] $REPO -> $DIR"
    git clone --depth=1 "$REPO" "$DIR"
  fi

  # Determine which git ref to checkout when REF is provided
  resolved_ref="${REF:-}"
  if [ "$resolved_ref" = "latest" ]; then
    echo "[INFO] REF=latest specified. Resolving latest git tag..."
    if git -C "$DIR" fetch --tags --quiet; then
      latest_tag="$(git -C "$DIR" tag --list 'v*' | sort -V | tail -n 1)"
      if [ -n "$latest_tag" ]; then
        echo "[INFO] Latest tag detected: $latest_tag"
        resolved_ref="$latest_tag"
      else
        echo "[WARN] No version tags (v*) found. Falling back to default branch."
        resolved_ref=""
      fi
    else
      echo "[WARN] Failed to fetch tags. Falling back to default branch."
      resolved_ref=""
    fi
  fi

  if [ -n "$resolved_ref" ]; then
    echo "[CHECKOUT] $resolved_ref"
    git -C "$DIR" fetch --depth=1 origin "$resolved_ref" || true
    git -C "$DIR" checkout -q "$resolved_ref"
  fi

  # Adjust Docker image tags based on REF semantics
  if [ "${REF:-}" = "latest" ]; then
    # For REF=latest, use 'latest' image tag regardless of resolved git tag
    update_image_tags "latest"
  elif [ -n "${REF:-}" ]; then
    # For specific ref (e.g. v1.0.0), use that as image tag
    update_image_tags "$REF"
  fi

  if [ -f "$DIR/tgo.sh" ]; then
    echo "[RUN] (cd $DIR && ./tgo.sh install)"
    (cd "$DIR" && ./tgo.sh install)
  else
    echo "[FATAL] Neither tgo.sh nor deploy.sh found in $DIR" >&2
    exit 1
  fi

  echo "\n[HINT] Use 'docker compose ps' inside $DIR to see status, and 'docker compose logs -f <service>' to tail logs."
}

main "$@"

