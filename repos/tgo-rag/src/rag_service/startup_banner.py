"""
Beautiful startup banner and enhanced logging utilities for the RAG service.
"""

import sys
from datetime import datetime
from typing import Dict, Any, Optional

from .logging_config import get_logger

# Try to import colorama for colored output, fallback to no colors if not available
try:
    from colorama import Fore, Back, Style, init
    # Initialize colorama for cross-platform colored output
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    # Fallback: no colors
    class _NoColor:
        def __getattr__(self, name):
            return ""

    Fore = Back = Style = _NoColor()
    COLORAMA_AVAILABLE = False

logger = get_logger(__name__)

# Color constants
class Colors:
    """Color constants for console output."""
    SUCCESS = Fore.GREEN
    INFO = Fore.CYAN
    WARNING = Fore.YELLOW
    ERROR = Fore.RED
    HEADER = Fore.MAGENTA
    ACCENT = Fore.BLUE
    RESET = Style.RESET_ALL
    BRIGHT = Style.BRIGHT
    DIM = Style.DIM

# Status symbols
class Symbols:
    """Unicode symbols for different statuses."""
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    ROCKET = "🚀"
    DATABASE = "🗄️"
    NETWORK = "🌐"
    GEAR = "⚙️"
    SHIELD = "🛡️"
    SPARKLES = "✨"
    CHECKMARK = "✓"
    CROSS = "✗"
    ARROW = "→"
    BULLET = "•"


def print_startup_banner(app_name: str, version: str, environment: str) -> None:
    """
    Print an attractive ASCII art banner for the RAG service.
    
    Args:
        app_name: Application name
        version: Application version
        environment: Current environment
    """
    # Clear the screen for a clean start (optional)
    # print("\033[2J\033[H", end="")
    
    banner = f"""
{Colors.BRIGHT}{Colors.HEADER}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  {Colors.BRIGHT}{Colors.ACCENT}████████╗ ██████╗  ██████╗       ██████╗  █████╗  ██████╗{Colors.HEADER}              ║
║  {Colors.BRIGHT}{Colors.ACCENT}╚══██╔══╝██╔════╝ ██╔═══██╗      ██╔══██╗██╔══██╗██╔════╝{Colors.HEADER}              ║
║  {Colors.BRIGHT}{Colors.ACCENT}   ██║   ██║  ███╗██║   ██║█████╗██████╔╝███████║██║  ███╗{Colors.HEADER}             ║
║  {Colors.BRIGHT}{Colors.ACCENT}   ██║   ██║   ██║██║   ██║╚════╝██╔══██╗██╔══██║██║   ██║{Colors.HEADER}             ║
║  {Colors.BRIGHT}{Colors.ACCENT}   ██║   ╚██████╔╝╚██████╔╝      ██║  ██║██║  ██║╚██████╔╝{Colors.HEADER}             ║
║  {Colors.BRIGHT}{Colors.ACCENT}   ╚═╝    ╚═════╝  ╚═════╝       ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝{Colors.HEADER}              ║
║                                                                              ║
║  {Colors.BRIGHT}{Colors.SUCCESS}Retrieval-Augmented Generation Service{Colors.HEADER}                               ║
║                                                                              ║
║  {Colors.INFO}Version: {Colors.BRIGHT}{version:<10}{Colors.HEADER} {Colors.INFO}Environment: {Colors.BRIGHT}{environment.upper():<12}{Colors.HEADER}                    ║
║  {Colors.INFO}Started: {Colors.BRIGHT}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.HEADER}                                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.RESET}"""
    
    print(banner)


def print_section_header(title: str, symbol: str = Symbols.GEAR) -> None:
    """
    Print a styled section header.
    
    Args:
        title: Section title
        symbol: Unicode symbol for the section
    """
    print(f"\n{Colors.BRIGHT}{Colors.HEADER}┌─ {symbol} {title} {Colors.HEADER}{'─' * (60 - len(title))}")


def print_section_footer() -> None:
    """Print a section footer."""
    print(f"{Colors.HEADER}└{'─' * 70}{Colors.RESET}")


def print_step(message: str, status: str = "info", indent: int = 0) -> None:
    """
    Print a startup step with appropriate styling.
    
    Args:
        message: Step message
        status: Status type (info, success, warning, error)
        indent: Indentation level
    """
    indent_str = "  " * indent
    
    if status == "success":
        symbol = Symbols.SUCCESS
        color = Colors.SUCCESS
    elif status == "error":
        symbol = Symbols.ERROR
        color = Colors.ERROR
    elif status == "warning":
        symbol = Symbols.WARNING
        color = Colors.WARNING
    else:
        symbol = Symbols.INFO
        color = Colors.INFO
    
    print(f"{Colors.HEADER}│{Colors.RESET} {indent_str}{symbol} {color}{message}{Colors.RESET}")


def print_config_info(config_data: Dict[str, Any]) -> None:
    """
    Print configuration information in a structured format.
    
    Args:
        config_data: Dictionary of configuration key-value pairs
    """
    print_section_header("Configuration", Symbols.GEAR)
    
    for key, value in config_data.items():
        # Mask sensitive information
        if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
            if isinstance(value, str) and len(value) > 8:
                display_value = f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
            else:
                display_value = "***"
        else:
            display_value = str(value)
        
        print(f"{Colors.HEADER}│{Colors.RESET}   {Colors.INFO}{key}:{Colors.RESET} {Colors.BRIGHT}{display_value}{Colors.RESET}")
    
    print_section_footer()


def print_startup_summary(
    host: str,
    port: int,
    environment: str,
    docs_enabled: bool = True,
    dev_project_created: bool = False
) -> None:
    """
    Print a startup summary with service information.
    
    Args:
        host: Server host
        port: Server port
        environment: Current environment
        docs_enabled: Whether API documentation is enabled
        dev_project_created: Whether development project was created
    """
    base_url = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://localhost:{port}"
    
    print_section_header("Service Ready", Symbols.ROCKET)
    
    print(f"{Colors.HEADER}│{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}   {Symbols.SPARKLES} {Colors.BRIGHT}{Colors.SUCCESS}TGO RAG Service is now running!{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}   {Colors.INFO}Service Endpoints:{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.NETWORK} Health Check: {Colors.BRIGHT}{base_url}/health{Colors.RESET}")
    
    if docs_enabled:
        print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.INFO} API Docs (Swagger): {Colors.BRIGHT}{base_url}/docs{Colors.RESET}")
        print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.INFO} API Docs (ReDoc): {Colors.BRIGHT}{base_url}/redoc{Colors.RESET}")
        print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.INFO} OpenAPI Spec: {Colors.BRIGHT}{base_url}/openapi.json{Colors.RESET}")
    
    print(f"{Colors.HEADER}│{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}   {Colors.INFO}API Endpoints:{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.BULLET} Collections: {Colors.BRIGHT}{base_url}/v1/collections{Colors.RESET}")
    print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.BULLET} Files: {Colors.BRIGHT}{base_url}/v1/files{Colors.RESET}")
    
    if environment.lower() == "development":
        print(f"{Colors.HEADER}│{Colors.RESET}")
        print(f"{Colors.HEADER}│{Colors.RESET}   {Colors.WARNING}Development Mode:{Colors.RESET}")
        if dev_project_created:
            print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.SUCCESS} Development project created")
        print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.SHIELD} Use API key: {Colors.BRIGHT}'dev'{Colors.RESET}")
        print(f"{Colors.HEADER}│{Colors.RESET}     {Symbols.INFO} Example: {Colors.DIM}curl -H 'X-API-Key: dev' {base_url}/v1/collections{Colors.RESET}")
    
    print(f"{Colors.HEADER}│{Colors.RESET}")
    print_section_footer()
    
    print(f"\n{Colors.BRIGHT}{Colors.SUCCESS}{Symbols.CHECKMARK} Startup completed successfully!{Colors.RESET}\n")


def log_startup_step(message: str, **kwargs) -> None:
    """
    Log a startup step with structured logging and console output.
    
    Args:
        message: Log message
        **kwargs: Additional structured logging fields
    """
    # Log to structured logger
    logger.info(message, **kwargs)
    
    # Also print to console with styling
    print_step(message, status="info")


def log_startup_success(message: str, **kwargs) -> None:
    """
    Log a successful startup step.
    
    Args:
        message: Log message
        **kwargs: Additional structured logging fields
    """
    logger.info(message, **kwargs)
    print_step(message, status="success")


def log_startup_error(message: str, **kwargs) -> None:
    """
    Log a startup error.
    
    Args:
        message: Log message
        **kwargs: Additional structured logging fields
    """
    logger.error(message, **kwargs)
    print_step(message, status="error")


def log_startup_warning(message: str, **kwargs) -> None:
    """
    Log a startup warning.
    
    Args:
        message: Log message
        **kwargs: Additional structured logging fields
    """
    logger.warning(message, **kwargs)
    print_step(message, status="warning")
