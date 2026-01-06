"""Plugin Installer Service - Handles downloading, building and installing plugins."""

import os
import shutil
import asyncio
import subprocess
import platform
from typing import Optional, Tuple, Any
from pathlib import Path

from app.core.logging import get_logger
from app.schemas.install import PluginInstallRequest, PluginSourceConfig, PluginBuildConfig

logger = get_logger("services.installer")


class PluginInstaller:
    """Service for installing and uninstalling plugins."""

    def __init__(self, base_path: str = "/var/lib/tgo/plugins"):
        self.base_path = Path(base_path)
        self.temp_path = self.base_path / "temp"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure necessary directories exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)

    async def install(self, request: PluginInstallRequest) -> Tuple[bool, str, Optional[str]]:
        """
        Install a plugin based on the request.
        
        Returns:
            (success, message, install_path)
        """
        plugin_id = request.id
        install_dir = self.base_path / plugin_id
        
        # Clean up existing installation if it exists
        if install_dir.exists():
            shutil.rmtree(install_dir)
        
        install_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if request.source.github:
                success, message = await self._install_from_github(plugin_id, install_dir, request.source.github, request.build)
            elif request.source.binary:
                success, message = await self._install_from_binary(plugin_id, install_dir, request.source.binary)
            else:
                return False, "No source configuration provided", None
            
            if success:
                return True, "Installation successful", str(install_dir)
            else:
                # Cleanup on failure
                if install_dir.exists():
                    shutil.rmtree(install_dir)
                return False, message, None
                
        except Exception as e:
            logger.exception(f"Unexpected error during installation of {plugin_id}: {e}")
            if install_dir.exists():
                shutil.rmtree(install_dir)
            return False, f"Unexpected error: {str(e)}", None

    async def _install_from_github(
        self, 
        plugin_id: str, 
        install_dir: Path, 
        github_config: Any, 
        build_config: Optional[PluginBuildConfig]
    ) -> Tuple[bool, str]:
        """Clone and build from GitHub."""
        repo_url = f"https://github.com/{github_config.repo}.git"
        temp_repo_path = self.temp_path / f"{plugin_id}_{os.getpid()}"
        
        if temp_repo_path.exists():
            shutil.rmtree(temp_repo_path)
            
        try:
            # Clone repo
            logger.info(f"Cloning {repo_url} (ref: {github_config.ref})")
            clone_cmd = ["git", "clone", "-b", github_config.ref, repo_url, str(temp_repo_path)]
            try:
                process = await asyncio.create_subprocess_exec(
                    *clone_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
            except FileNotFoundError:
                return False, "System error: 'git' command not found. Please ensure git is installed in the runtime environment."
            
            if process.returncode != 0:
                return False, f"Git clone failed: {stderr.decode()}"
            
            # Move to target path
            source_path = temp_repo_path
            if github_config.path and github_config.path != "/":
                source_path = temp_repo_path / github_config.path.lstrip("/")
            
            if not source_path.exists():
                return False, f"Source path {github_config.path} not found in repo"
            
            # Copy all files to install dir
            for item in source_path.iterdir():
                if item.is_dir():
                    shutil.copytree(item, install_dir / item.name)
                else:
                    shutil.copy2(item, install_dir / item.name)
            
            # Build if needed
            if build_config:
                return await self._build_plugin(plugin_id, install_dir, build_config)
            
            return True, "Source installed successfully"
            
        finally:
            if temp_repo_path.exists():
                shutil.rmtree(temp_repo_path)

    async def _install_from_binary(self, plugin_id: str, install_dir: Path, binary_config: Any) -> Tuple[bool, str]:
        """Download and install binary."""
        # Replace variables in URL
        url = binary_config.url
        system = platform.system().lower()
        if system == "darwin":
            system = "darwin"
        elif system == "windows":
            system = "windows"
        else:
            system = "linux"
            
        arch = platform.machine().lower()
        if arch in ("x86_64", "amd64"):
            arch = "amd64"
        elif arch in ("arm64", "aarch64"):
            arch = "arm64"
            
        url = url.replace("${os}", system).replace("${arch}", arch)
        
        logger.info(f"Downloading binary from {url}")
        
        temp_file = self.temp_path / f"{plugin_id}_bin"
        try:
            # Use curl to download
            download_cmd = ["curl", "-L", "-o", str(temp_file), url]
            try:
                process = await asyncio.create_subprocess_exec(
                    *download_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
            except FileNotFoundError:
                return False, "System error: 'curl' command not found. Please ensure curl is installed."
            
            if process.returncode != 0:
                return False, f"Download failed: {stderr.decode()}"
            
            # Check if it's an archive (zip/tar.gz)
            # For simplicity, assume if it ends in .zip or .tar.gz it's an archive
            if url.endswith(".zip"):
                unpack_cmd = ["unzip", "-o", str(temp_file), "-d", str(install_dir)]
                process = await asyncio.create_subprocess_exec(*unpack_cmd)
                await process.wait()
            elif url.endswith(".tar.gz") or url.endswith(".tgz"):
                unpack_cmd = ["tar", "-xzf", str(temp_file), "-C", str(install_dir)]
                process = await asyncio.create_subprocess_exec(*unpack_cmd)
                await process.wait()
            else:
                # Just a single binary
                target_bin = install_dir / "plugin"
                shutil.copy2(temp_file, target_bin)
                target_bin.chmod(0o755)
            
            return True, "Binary installed successfully"
            
        finally:
            if temp_file.exists():
                temp_file.unlink()

    async def _build_plugin(self, plugin_id: str, install_dir: Path, build_config: PluginBuildConfig) -> Tuple[bool, str]:
        """Build plugin based on language."""
        lang = build_config.language.lower()
        
        if lang == "go":
            if not build_config.go:
                return False, "Missing Go build configuration"
            
            logger.info(f"Building Go plugin {plugin_id}")
            cmd = ["go", "build", "-o", build_config.go.output, build_config.go.main]
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(install_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
            except FileNotFoundError:
                return False, "System error: 'go' compiler not found. Please ensure Go is installed."
            
            if process.returncode != 0:
                return False, f"Go build failed: {stderr.decode()}"
            
            return True, "Go build successful"
            
        elif lang == "python":
            if not build_config.python:
                return False, "Missing Python build configuration"
            
            logger.info(f"Installing Python dependencies for {plugin_id}")
            # Create venv
            venv_dir = install_dir / ".venv"
            cmd_venv = ["python3", "-m", "venv", str(venv_dir)]
            try:
                process = await asyncio.create_subprocess_exec(*cmd_venv)
                await process.wait()
            except FileNotFoundError:
                return False, "System error: 'python3' not found or 'venv' module missing."
            
            # Install requirements
            req_file = build_config.python.requirements
            if (install_dir / req_file).exists():
                pip_path = str(venv_dir / "bin" / "pip")
                cmd_pip = [pip_path, "install", "-r", req_file]
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd_pip,
                        cwd=str(install_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                except FileNotFoundError:
                    return False, "System error: 'pip' not found in virtual environment."
                
                if process.returncode != 0:
                    return False, f"Python pip install failed: {stderr.decode()}"
            
            return True, "Python setup successful"
            
        elif lang == "nodejs":
            if not build_config.nodejs:
                return False, "Missing Node.js build configuration"
            
            logger.info(f"Installing Node.js dependencies for {plugin_id}")
            if (install_dir / build_config.nodejs.package).exists():
                cmd = ["npm", "install"]
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        cwd=str(install_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                except FileNotFoundError:
                    return False, "System error: 'npm' command not found. Please ensure Node.js is installed."
                
                if process.returncode != 0:
                    return False, f"npm install failed: {stderr.decode()}"
            
            return True, "Node.js setup successful"
            
        return False, f"Unsupported language: {lang}"

    async def uninstall(self, plugin_id: str) -> bool:
        """Uninstall a plugin."""
        install_dir = self.base_path / plugin_id
        if install_dir.exists():
            shutil.rmtree(install_dir)
            logger.info(f"Uninstalled plugin {plugin_id}")
            return True
        return False


# Global instance
installer = PluginInstaller()

