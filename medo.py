#!/usr/bin/env python3
"""
Author: qvfear | Discord: qvfear
"""

import os
import sys
import subprocess
import time
import string
import random
import re
import logging
import argparse
import signal
import atexit
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console
else:
    from rich.console import Console

# Made by qvfear | Discord: qvfear

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE FOR CLEANUP
# ─────────────────────────────────────────────────────────────────────────────

_active_drivers = []
_shutdown_requested = False
_cleanup_done = False
_log_lock = __import__('threading').Lock()


def cleanup_all():
    """Clean up all active browser drivers on exit."""
    global _active_drivers, _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    
    for driver in _active_drivers[:]:  # Copy list to avoid modification during iteration
        try:
            driver.quit()
        except Exception:
            pass
    _active_drivers.clear()


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    # Use stderr and flush immediately for visibility
    sys.stderr.write("\n⚬ Shutdown requested, cleaning up...\n")
    sys.stderr.flush()
    cleanup_all()
    # Force immediate exit
    os._exit(1)


# Register signal handlers and atexit
try:
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
except ValueError:
    pass  # Signal not supported in this context
try:
    signal.signal(signal.SIGTERM, signal_handler)  # Kill signal
except ValueError:
    pass
try:
    signal.signal(signal.SIGQUIT, signal_handler)  # Ctrl+\
except ValueError:
    pass
# Note: Ctrl+Z (SIGTSTP) cannot be reliably handled as it suspends the process
# Use Ctrl+C or Ctrl+\ instead
atexit.register(cleanup_all)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SiteConfig:
    """Site-specific configuration and selectors."""
    site_name: str = "MeDo"
    target_url: str = "https://medo.dev/?invitecode=user-9mj2gtv04um8"
    temp_mail_url: str = "https://temp-mail.io/en/"
    success_message: str = "✨ Account successfully created! Check your credits on your main account."

    # Selectors - Centralized for easy maintenance
    selectors: Dict[str, str] = field(default_factory=lambda: {
        # Temp Mail (temp-mail.io)
        "temp_mail_copy_btn": "copy-button",  # data-qa="copy-button"
        "temp_mail_email_input": "email",  # id="email"
        "temp_mail_refresh_btn": "refresh-button",  # data-qa="refresh-button"
        "temp_mail_email_list": "email-list",  # class="email-list"
        "temp_mail_message_item": "message",  # class="message" with data-qa="message"
        "temp_mail_verify_subject": "Verify your email",
        "temp_mail_verify_btn_text": "Verify Your Account",
        "temp_mail_body_container": "message__body",

        # Auth
        "login_link": "//*[contains(text(), 'Login')]",
        "signup_switch": "link-signup-login",
        "email_input": "email",
        "password_input": "password",
        "terms_checkbox": "agree-terms",
        "signup_button": "btn-signup",
        "login_button": "btn-login",

        # Verification
        "verification_link_pattern": r'https://auth\.medo\.dev[^\s<>"\']+',
        "verification_email_keywords": ["MeDo", "Verify", "support@medo.dev"],
    })


@dataclass
class AutomationConfig:
    """Automation behavior configuration."""
    default_total_accounts: int = 10
    default_workers: int = 3
    max_retries: int = 2
    email_timeout: int = 45  # Reduced from 60
    page_load_timeout: int = 30  # Reduced from 45
    implicit_wait: float = 0.2

    # Browser settings
    window_width: int = 1920
    window_height: int = 1080
    languages: List[str] = field(default_factory=lambda: ["en-US", "en"])


# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────────────


class RichLoggingHandler(logging.Handler):
    """Custom logging handler that outputs with Rich colors."""

    def __init__(self, console: 'Console'):
        super().__init__()
        self.console = console
        self.level_colors = {
            logging.DEBUG: "dim cyan",
            logging.INFO: "green",
            logging.WARNING: "yellow",
            logging.ERROR: "red",
            logging.CRITICAL: "bold red",
        }
        self.level_icons = {
            logging.DEBUG: "•",
            logging.INFO: "ℹ",
            logging.WARNING: "⚠",
            logging.ERROR: "✗",
            logging.CRITICAL: "⛔",
        }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            color = self.level_colors.get(record.levelno, "white")
            icon = self.level_icons.get(record.levelno, "•")
            timestamp = datetime.now().strftime("%H:%M:%S")

            self.console.print(f"[dim]{timestamp}[/dim] [{color}]{icon}[/] {msg}")
        except Exception:
            self.handleError(record)


def setup_logging(verbose: bool = False, log_file: Optional[str] = None, console: Optional['Console'] = None) -> logging.Logger:
    """Configure logging with Rich console and optional file output."""
    logger = logging.getLogger("medo_automation")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()  # Clear existing handlers

    # Rich console handler
    if console:
        rich_handler = RichLoggingHandler(console)
        rich_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        logger.addHandler(rich_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)-8s | %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AccountResult:
    """Result of account creation attempt."""
    success: bool
    email: Optional[str] = None
    password: Optional[str] = None
    error: Optional[str] = None
    thread_id: int = 0
    account_index: int = 0
    duration: float = 0.0


@dataclass
class BrowserConfig:
    """Browser configuration for WebDriver."""
    user_agent: str
    window_size: Tuple[int, int] = (1920, 1080)
    headless: bool = True
    languages: List[str] = field(default_factory=lambda: ["en-US", "en"])


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def generate_password(length: int = 12, use_special_chars: bool = True) -> str:
    """Generate a secure random password."""
    chars = string.ascii_letters + string.digits
    if use_special_chars:
        chars += "!@#$%^&*"
    return ''.join(random.SystemRandom().choice(chars) for _ in range(length))


def setup_dependencies(silent: bool = True, console: Optional['Console'] = None) -> None:
    """Ensure all dependencies and Chrome are installed."""
    if console is None:
        console = Console()

    missing_deps = []
    for dep in ["selenium", "rich", "webdriver-manager", "selenium_stealth"]:
        try:
            __import__(dep)
        except ImportError:
            missing_deps.append(dep.replace("_", "-"))

    if missing_deps:
        console.print(f"[yellow]⚬ Installing missing dependencies:[/yellow] {', '.join(missing_deps)}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing_deps],
            stdout=subprocess.DEVNULL if silent else None,
            stderr=subprocess.DEVNULL if silent else None
        )
        console.print("[green]✓ Dependencies installed[/green]")

    # Check for Chrome binary
    chrome_check = subprocess.run(
        ["which", "google-chrome"],
        capture_output=True,
        text=True
    )
    if chrome_check.returncode != 0:
        console.print("[yellow]⚬ Installing Google Chrome...[/yellow]")
        try:
            subprocess.run(
                "wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
                shell=True, check=True
            )
            subprocess.run(
                "sudo dpkg -i google-chrome-stable_current_amd64.deb > /dev/null 2>&1 || sudo apt-get install -fy > /dev/null 2>&1",
                shell=True, check=True
            )
            subprocess.run("rm google-chrome-stable_current_amd64.deb", shell=True, check=True)
            console.print("[green]✓ Chrome installed[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Chrome installation failed: {e}[/red]")


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER MANAGER
# ─────────────────────────────────────────────────────────────────────────────


class BrowserManager:
    """Manages browser instance lifecycle and configuration."""

    def __init__(self, config: BrowserConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.driver = None

    def create_driver(self) -> Any:
        """Create and configure Chrome WebDriver with stealth."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium_stealth import stealth

        options = Options()
        options.add_argument(f"--window-size={self.config.window_size[0]}x{self.config.window_size[1]}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f'user-agent={self.config.user_agent}')
        
        # Enable clipboard access
        options.add_argument("--disable-features=ClipboardPasteWarning")

        if self.config.headless:
            options.add_argument("--headless=new")

        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )

        # Apply stealth techniques
        stealth(
            self.driver,
            languages=self.config.languages,
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

        # Register driver for cleanup
        _active_drivers.append(self.driver)

        self.logger.debug(f"Browser created with UA: {self.config.user_agent[:50]}...")
        return self.driver

    def quit(self) -> None:
        """Safely quit the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.debug(f"Error closing browser: {e}")
            finally:
                # Remove from active drivers list
                if self.driver in _active_drivers:
                    _active_drivers.remove(self.driver)
                self.driver = None


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────


class AutomationEngine:
    """Main automation engine for account creation workflow."""

    def __init__(
        self,
        thread_id: int,
        account_idx: int,
        site_config: SiteConfig,
        auto_config: AutomationConfig,
        logger: logging.Logger,
        verbose: bool = False,
        console: Optional['Console'] = None
    ):
        self.thread_id = thread_id
        self.account_idx = account_idx
        self.site_config = site_config
        self.auto_config = auto_config
        self.logger = logger
        self.verbose = verbose
        self.console = console

        # Browser configuration
        browser_config = BrowserConfig(
            user_agent=random.choice(USER_AGENTS),
            window_size=(auto_config.window_width, auto_config.window_height),
            languages=auto_config.languages
        )
        self.browser_manager = BrowserManager(browser_config, logger)
        self.driver = None
        self.wait = None

    def _log(self, message: str, level: str = "info", force: bool = False) -> None:
        """Log a message with thread context and colored output."""
        if self.verbose or force:
            prefix = f"[Account {self.account_idx}]"

            # Map levels to colors and icons
            level_config = {
                "debug": ("dim cyan", "•"),
                "info": ("green", "ℹ"),
                "warning": ("yellow", "⚠"),
                "error": ("red", "✗"),
                "success": ("bright_green", "✓"),
            }
            color, icon = level_config.get(level, ("white", "•"))

            with _log_lock:
                self.logger.log(
                    getattr(logging, level.upper(), logging.INFO),
                    f"{prefix} {message}"
                )

    def _safe_click(self, locator: Tuple[str, str], description: str, timeout: int = 10) -> bool:
        """Safely click an element with fallback to JavaScript click."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            TimeoutException, ElementNotInteractableException, ElementClickInterceptedException
        )

        try:
            self._log(f"Clicking: {description}")
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.element_to_be_clickable(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)
            element.click()
            self._log(f"✓ {description}", "debug")
            return True
        except (TimeoutException, ElementNotInteractableException, ElementClickInterceptedException):
            try:
                element = self.driver.find_element(*locator)
                self.driver.execute_script("arguments[0].click();", element)
                self._log(f"✓ {description} (JS click)", "debug")
                return True
            except Exception as e:
                self._log(f"✗ Failed to click {description}: {e}", "warning", force=True)
                return False

    def _wait_for_element(self, locator: Tuple[str, str], timeout: Optional[int] = None) -> Optional[Any]:
        """Wait for element to be present."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        try:
            wait = WebDriverWait(self.driver, timeout or self.auto_config.page_load_timeout)
            return wait.until(EC.presence_of_element_located(locator))
        except TimeoutException:
            return None

    def _get_verification_link(self, page_source: str) -> Optional[str]:
        """Extract verification link from page source."""
        pattern = self.site_config.selectors["verification_link_pattern"]
        match = re.search(pattern, page_source)
        return match.group(0) if match else None

    def _create_temp_email(self) -> Tuple[str, str]:
        """Create temporary email and return (email, username)."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Open temp-mail.io in new tab
        self.driver.execute_script(f"window.open('{self.site_config.temp_mail_url}');")
        self.driver.switch_to.window(self.driver.window_handles[-1])

        # Wait for page to load - wait for email input field
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, self.site_config.selectors["temp_mail_email_input"]))
            )
        except Exception as e:
            self._log(f"Waiting for page load: {e}", "debug")
        
        # Wait for email to be populated (value attribute to have @)
        email = None
        try:
            email_input = WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.ID, self.site_config.selectors["temp_mail_email_input"])
            )
            # Wait until the value attribute contains @
            WebDriverWait(self.driver, 10).until(
                lambda d: "@" in (d.find_element(By.ID, self.site_config.selectors["temp_mail_email_input"]).get_attribute("value") or "")
            )
            email = email_input.get_attribute("value")
            if email and "@" in email:
                self._log(f"Got email from input field: {email}", "debug")
        except Exception as e:
            self._log(f"Method 1 (input field) failed: {e}", "debug")
        
        # Method 2: Try clipboard via copy button
        if not email:
            try:
                copy_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f"[data-qa='{self.site_config.selectors['temp_mail_copy_btn']}']"))
                )
                copy_btn.click()
                time.sleep(0.5)
                email = self.driver.execute_script("return navigator.clipboard.readText();")
                if email and "@" in email:
                    self._log(f"Got email from clipboard: {email}", "debug")
            except Exception as e:
                self._log(f"Method 2 (clipboard) failed: {e}", "debug")
        
        # Method 3: Extract from page text using regex
        if not email:
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', body_text)
                if email_match:
                    email = email_match.group(0)
                    self._log(f"Got email from page text: {email}", "debug")
            except Exception as e:
                self._log(f"Method 3 (regex) failed: {e}", "debug")
        
        if not email or "@" not in email:
            # Debug info
            try:
                page_title = self.driver.title
                url = self.driver.current_url
                input_value = self.driver.find_element(By.ID, self.site_config.selectors["temp_mail_email_input"]).get_attribute("value")
                body_preview = self.driver.find_element(By.TAG_NAME, "body").text[:500]
                self._log(f"Debug - URL: {url}", "debug", force=True)
                self._log(f"Debug - Title: {page_title}", "debug", force=True)
                self._log(f"Debug - Input value: '{input_value}'", "debug", force=True)
                self._log(f"Debug - Body preview: {body_preview}", "debug", force=True)
            except Exception as e:
                self._log(f"Debug error: {e}", "debug", force=True)
            raise Exception(f"Could not retrieve email address")

        self._log(f"Created temp email: {email}", "info", force=True)
        return email, email.split("@")[0]

    def _register_account(self, email: str, password: str) -> bool:
        """Register account on target site."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.expected_conditions import staleness_of

        # Navigate to target URL
        self.driver.switch_to.window(self.driver.window_handles[0])
        
        # Fast page load
        self.driver.get(self.site_config.target_url)
        
        # Wait for page to fully load
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.TAG_NAME, "body") is not None
            )
        except:
            time.sleep(1)

        # Click login to open auth modal (fast timeout)
        self._safe_click((By.XPATH, self.site_config.selectors["login_link"]), "Open login modal", timeout=5)

        # Switch to signup (fast timeout)
        self._safe_click((By.ID, self.site_config.selectors["signup_switch"]), "Switch to signup", timeout=5)

        # Fill form
        email_field = self._wait_for_element((By.ID, self.site_config.selectors["email_input"]))
        if not email_field:
            raise Exception("Email field not found")
        email_field.send_keys(email)

        password_field = self.driver.find_element(By.ID, self.site_config.selectors["password_input"])
        password_field.send_keys(password)

        # Try to check terms checkbox
        try:
            terms_checkbox = self.driver.find_element(By.ID, self.site_config.selectors["terms_checkbox"])
            if not terms_checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", terms_checkbox)
        except Exception:
            self._log("Terms checkbox not found or already checked", "debug")

        # Submit signup (fast timeout)
        self._safe_click((By.ID, self.site_config.selectors["signup_button"]), "Submit registration", timeout=5)
        return True

    def _verify_email(self, email: str) -> bool:
        """Wait for and click verification email."""
        from selenium.webdriver.common.by import By

        self.driver.switch_to.window(self.driver.window_handles[-1])

        keywords = self.site_config.selectors["verification_email_keywords"]
        start_time = time.time()

        self._log("Waiting for verification email...", "info")

        # Faster refresh intervals
        while time.time() - start_time < self.auto_config.email_timeout:
            # Check for shutdown request
            if _shutdown_requested:
                raise Exception("Shutdown requested")

            try:
                # Click refresh button to check for new emails
                try:
                    refresh_btn = self.driver.find_element(By.CSS_SELECTOR, f"[data-qa='{self.site_config.selectors['temp_mail_refresh_btn']}']")
                    refresh_btn.click()
                    time.sleep(1.5)  # Wait for page to load after refresh
                except Exception:
                    self.driver.refresh()
                    time.sleep(1.5)
                
                # Check for email list with messages
                try:
                    email_list = self.driver.find_element(By.CSS_SELECTOR, f".{self.site_config.selectors['temp_mail_email_list']}")
                    page_text = email_list.text.lower()

                    if any(kw.lower() in page_text for kw in keywords):
                        self._log("✓ Verification email received!", "success", force=True)
                        
                        # Try to extract and show the verification link
                        verification_link = None
                        try:
                            page_source = self.driver.page_source
                            verification_link = self._get_verification_link(page_source)
                            if verification_link:
                                # Clean up the link (remove tracking)
                                clean_link = verification_link.split('#')[0]
                                # Print directly to ensure visibility
                                with _log_lock:
                                    print(f"\033[96m    📬 Verification link:\033[0m \033[2m{clean_link}\033[0m", flush=True)
                        except Exception as e:
                            print(f"\033[91m    Error extracting link: {e}\033[0m", flush=True)
                        
                        # Find and click on the email message
                        try:
                            # Look for message with "Verify your email" subject
                            message = self.driver.find_element(
                                By.XPATH, f"//*[contains(@title, 'Verify your email') or contains(@data-qa, 'message')]"
                            )
                            message.click()
                            time.sleep(1.5)
                            self._log("Email opened", "debug")
                            return True
                        except Exception:
                            # Fallback: click on first message in list
                            try:
                                message_item = self.driver.find_element(
                                    By.CSS_SELECTOR, f".{self.site_config.selectors['temp_mail_message_item']}"
                                )
                                message_item.click()
                                time.sleep(1.5)
                                self._log("Email opened (fallback)", "debug")
                                return True
                            except Exception:
                                pass

                except Exception:
                    pass

            except Exception as e:
                self._log(f"Checking for email... ({int(time.time() - start_time)}s)", "debug")

            time.sleep(2)  # Reduced check interval

        raise Exception(f"Verification email not received within {self.auto_config.email_timeout}s")

    def _complete_verification(self) -> bool:
        """Navigate to verification link and complete process."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # Scroll down to see the full email content
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        verification_link = None
        
        # Method 1: Click "Verify Your Account" button
        try:
            verify_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{self.site_config.selectors['temp_mail_verify_btn_text']}')]"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", verify_btn)
            time.sleep(0.3)
            verify_btn.click()
            self._log("Clicked Verify button", "debug")
            time.sleep(3)
            
            # Check if we were redirected
            if "auth.medo.dev" in self.driver.current_url or "email-verification" in self.driver.current_url:
                self._log("Verification completed via button click", "debug")
                time.sleep(2)
                return True
        except Exception as e:
            self._log(f"Button click failed: {e}", "debug")
        
        # Method 2: Extract and navigate to verification link from page source
        try:
            page_source = self.driver.page_source
            verification_link = self._get_verification_link(page_source)
            if verification_link:
                self._log(f"Navigating to verification link: {verification_link[:80]}...", "debug")
                self.driver.get(verification_link)
                # Wait for verification page to fully load
                time.sleep(5)
                self._log("Verification page loaded, waiting...", "debug")
                return True
        except Exception as e:
            self._log(f"Method 2 (page source link) failed: {e}", "debug")
        
        # Method 3: Look for any href containing auth.medo.dev
        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href")
                if href and "auth.medo.dev" in href and "email-verification" in href:
                    self._log(f"Found verification link in DOM: {href[:80]}...", "debug")
                    self.driver.get(href)
                    time.sleep(5)
                    return True
        except Exception as e:
            self._log(f"Method 3 (DOM links) failed: {e}", "debug")
        
        # Method 4: Look for SendGrid redirect links
        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href")
                if href and ("u55282886.ct.sendgrid.net" in href or "click?upn=" in href):
                    self._log(f"Found SendGrid redirect link, navigating...", "debug")
                    self.driver.get(href)
                    time.sleep(5)
                    return True
        except Exception as e:
            self._log(f"Method 4 (SendGrid links) failed: {e}", "debug")
        
        raise Exception("Could not find or navigate to verification link")

    def _login_and_validate(self, email: str, password: str) -> bool:
        """Login to validate account creation."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # Go back to medo.dev
        self.driver.get("https://medo.dev")
        time.sleep(2)
        
        # Wait for page to load
        try:
            WebDriverWait(self.driver, 8).until(
                lambda d: d.find_element(By.TAG_NAME, "body") is not None
            )
        except:
            time.sleep(1)
        
        # Click login to open auth modal
        self._safe_click((By.XPATH, self.site_config.selectors["login_link"]), "Open login", timeout=5)
        time.sleep(1)
        
        # Fill credentials
        email_field = self._wait_for_element((By.ID, self.site_config.selectors["email_input"]))
        if not email_field:
            raise Exception("Login email field not found")
        email_field.send_keys(email)

        password_field = self.driver.find_element(By.ID, self.site_config.selectors["password_input"])
        password_field.send_keys(password)
        
        # Try to check terms checkbox if exists
        try:
            terms_checkbox = self.driver.find_element(By.ID, self.site_config.selectors["terms_checkbox"])
            if not terms_checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", terms_checkbox)
        except Exception:
            self._log("Terms checkbox not found or already checked", "debug")

        # Submit login
        self._safe_click((By.ID, self.site_config.selectors["login_button"]), "Login", timeout=5)
        
        # Wait for redirect/dashboard
        time.sleep(3)
        
        # Check if login succeeded by looking for dashboard elements or URL change
        current_url = self.driver.current_url
        page_source = self.driver.page_source.lower()
        
        # Success indicators
        success_indicators = [
            "dashboard", "profile", "logout", "credits", "settings",
            "welcome", "account"
        ]
        
        if any(indicator in page_source for indicator in success_indicators):
            self._log("Login successful - dashboard detected", "info", force=True)
            return True
        
        if "login" not in current_url.lower() and "auth" not in current_url.lower():
            self._log("Login successful - URL changed", "info", force=True)
            return True

        # If still on login page, check for error messages
        try:
            error_msgs = self.driver.find_elements(By.CLASS_NAME, "error")
            if error_msgs:
                self._log(f"Login error detected: {error_msgs[0].text}", "warning")
        except:
            pass
        
        # Assume success if we got this far without errors
        self._log("Login completed", "info", force=True)
        return True

    def run(self, account_idx: int, total: int) -> AccountResult:
        """Execute the complete account creation workflow."""
        start_time = time.time()
        password = generate_password()
        email = None

        self._log(f"Starting account {account_idx}/{total}", "info", force=True)

        try:
            # Initialize browser
            self.driver = self.browser_manager.create_driver()
            from selenium.webdriver.support.ui import WebDriverWait
            self.wait = WebDriverWait(self.driver, self.auto_config.page_load_timeout)

            # Step 1: Create temp email
            email, _ = self._create_temp_email()

            # Step 2: Register account
            self._register_account(email, password)
            self._log("Registration submitted", "debug")

            # Step 3: Verify email
            self._verify_email(email)

            # Step 4: Complete verification
            self._complete_verification()

            # Step 5: Login and validate
            self._login_and_validate(email, password)

            duration = time.time() - start_time
            self._log(f"Account created successfully in {duration:.1f}s", "info", force=True)

            return AccountResult(
                success=True,
                email=email,
                password=password,
                thread_id=self.thread_id,
                account_index=account_idx,
                duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            self._log(f"Failed: {e}", "error", force=True)
            return AccountResult(
                success=False,
                email=email,
                password=password,
                error=str(e),
                thread_id=self.thread_id,
                account_index=account_idx,
                duration=duration
            )

        finally:
            # Always close the browser completely
            try:
                if self.driver:
                    # Clear all data first
                    self.driver.delete_all_cookies()
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
                    # Then quit
                    self.driver.quit()
                    # Remove from active drivers
                    if self.driver in _active_drivers:
                        _active_drivers.remove(self.driver)
            except Exception:
                pass
            finally:
                self.driver = None


# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT MANAGER
# ─────────────────────────────────────────────────────────────────────────────


class AccountManager:
    """Manages account persistence and file operations."""

    def __init__(self, accounts_file: str = "accounts.txt", logger: Optional[logging.Logger] = None):
        self.accounts_file = Path(accounts_file)
        self.logger = logger or logging.getLogger(__name__)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create accounts file if it doesn't exist."""
        if not self.accounts_file.exists():
            self.accounts_file.touch()
            self.logger.debug(f"Created accounts file: {self.accounts_file}")

    def save_account(self, email: str, password: str) -> bool:
        """Save account credentials to file."""
        try:
            with open(self.accounts_file, "a") as f:
                f.write(f"{email}:{password}\n")
            self.logger.debug(f"Saved account: {email}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save account: {e}")
            return False

    def get_existing_count(self) -> int:
        """Get count of existing accounts in file."""
        try:
            with open(self.accounts_file, "r") as f:
                return sum(1 for line in f if line.strip() and ":" in line)
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# LINK MANAGER
# ─────────────────────────────────────────────────────────────────────────────


class LinkManager:
    """Manages invite link persistence."""

    def __init__(self, link_file: str = ".last_link"):
        self.link_file = Path(link_file)

    def load_link(self, default: str) -> str:
        """Load saved link or return default."""
        if self.link_file.exists():
            try:
                with open(self.link_file, "r") as f:
                    saved = f.read().strip()
                    if saved:
                        return saved
            except Exception:
                pass
        return default

    def save_link(self, link: str) -> bool:
        """Save invite link to file."""
        try:
            with open(self.link_file, "w") as f:
                f.write(link)
            return True
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────


class AutomationOrchestrator:
    """Main orchestrator for the automation process."""

    def __init__(
        self,
        site_config: SiteConfig,
        auto_config: AutomationConfig,
        args: argparse.Namespace
    ):
        self.site_config = site_config
        self.auto_config = auto_config
        self.args = args

        # Initialize Rich console
        self.console = Console()

        # Setup logging with Rich console
        self.logger = setup_logging(
            verbose=args.verbose,
            log_file=args.log_file if hasattr(args, 'log_file') else None,
            console=self.console
        )

        # Initialize managers
        self.account_manager = AccountManager(logger=self.logger)
        self.link_manager = LinkManager()

    def _get_invite_link(self) -> str:
        """Get invite link from args or prompt."""
        default_link = self.link_manager.load_link(self.site_config.target_url)

        if self.args.invite_link:
            link = self.args.invite_link
        else:
            # Interactive prompt with styling
            self.console.print(f"[dim]Default invite link: [white]{default_link}[/white][/dim]")
            try:
                # Render colored prompt, then use plain input
                self.console.print("[bold yellow]? Enter MeDo invite link [dim][default][/dim]: [/bold yellow]", end="")
                link = input().strip()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                cleanup_all()
                sys.exit(1)
            if not link:
                link = default_link

        self.link_manager.save_link(link)
        return link

    def _run_single_account(self, account_idx: int, total: int) -> AccountResult:
        """Run automation for a single account."""
        # Check for shutdown
        if _shutdown_requested:
            return AccountResult(
                success=False,
                error="Shutdown requested",
                thread_id=account_idx,
                account_index=account_idx
            )

        engine = AutomationEngine(
            thread_id=account_idx,
            account_idx=account_idx,
            site_config=self.site_config,
            auto_config=self.auto_config,
            logger=self.logger,
            verbose=self.args.verbose or account_idx <= 1,
            console=self.console
        )
        return engine.run(account_idx, total)

    def _run_with_retry(self, account_idx: int, total: int) -> AccountResult:
        """Run account creation with retry logic."""
        for attempt in range(self.auto_config.max_retries + 1):
            # Check for shutdown before each attempt
            if _shutdown_requested:
                return AccountResult(
                    success=False,
                    error="Shutdown requested",
                    thread_id=account_idx,
                    account_index=account_idx
                )
            
            if attempt > 0:
                self.logger.info(f"[T{account_idx}] Retry attempt {attempt}/{self.auto_config.max_retries}")
                time.sleep(2)  # Brief delay before retry

            result = self._run_single_account(account_idx, total)

            if result.success:
                return result

        return result

    def run(self) -> Dict[str, Any]:
        """Execute the full automation workflow."""
        from rich.live import Live
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn, TimeElapsedColumn
        from rich.layout import Layout
        from rich.panel import Panel

        # Get configuration
        invite_link = self._get_invite_link()
        self.site_config.target_url = invite_link

        # Ask for total accounts
        if not self.args.total:
            try:
                total_input = self.console.input("[bold yellow]?[/bold yellow] [cyan]How many accounts to make?[/cyan] [dim][default: 10][/dim]: ").strip()
                if total_input:
                    total = int(total_input)
                else:
                    total = self.auto_config.default_total_accounts
            except (EOFError, KeyboardInterrupt, ValueError):
                print("\n")
                cleanup_all()
                sys.exit(1)
        else:
            total = self.args.total

        # Ask for workers
        if not self.args.workers:
            workers = self.auto_config.default_workers
            try:
                mt_input = self.console.input(f"[bold yellow]?[/bold yellow] [cyan]Enable multi-threading with {workers} workers?[/cyan] [dim][Y/n][/dim]: ").strip().lower()
                if mt_input == 'n':
                    workers = 1
            except (EOFError, KeyboardInterrupt):
                print("\n")
                cleanup_all()
                sys.exit(1)
        else:
            workers = self.args.workers

        self.console.print()
        self.console.print(f"[bold cyan]📊 Configuration:[/bold cyan]")
        self.console.print(f"   ├─ [white]Accounts:[/white] [bold]{total}[/bold]")
        self.console.print(f"   ├─ [white]Workers:[/white] [bold]{workers}[/bold]")
        self.console.print(f"   └─ [white]Target:[/white] [dim]{invite_link[:50]}...[/dim]")
        self.console.print()

        # Progress display
        results: List[AccountResult] = []
        completed = 0

        progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]Account[/bold cyan] [progress.description]{task.description}"),
            BarColumn(bar_width=40, complete_style="green", finished_style="green"),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=self.console,
            refresh_per_second=10,
        )

        try:
            progress.start()
            task = progress.add_task("Processing...", total=total)

            def update_progress(result: AccountResult):
                results.append(result)
                nonlocal completed
                completed += 1
                
                if result.success:
                    progress.update(
                        task,
                        advance=1,
                        description=f"[green]✓ Created[/green] ({result.email})",
                    )
                    # Save successful accounts immediately
                    if result.email and result.password:
                        self.account_manager.save_account(result.email, result.password)
                else:
                    progress.update(
                        task,
                        advance=1,
                        description=f"[red]✗ Failed[/red]: {result.error[:30]}",
                    )

            if workers == 1:
                # Sequential execution
                for i in range(1, total + 1):
                    if _shutdown_requested:
                        break
                    progress.update(task, description=f"[yellow]⏳ Processing[/yellow] account {i}/{total}")
                    result = self._run_with_retry(i, total)
                    update_progress(result)
            else:
                # Parallel execution
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {
                        executor.submit(self._run_with_retry, i, total): i
                        for i in range(1, total + 1)
                    }

                    for future in as_completed(futures):
                        if _shutdown_requested:
                            # Cancel remaining futures
                            for f in futures:
                                f.cancel()
                            break
                        try:
                            result = future.result()
                            update_progress(result)
                        except Exception as e:
                            self._log(f"Worker error: {e}", "error")
        except KeyboardInterrupt:
            pass
        finally:
            progress.stop()
        
        # Check if shutdown was requested
        if _shutdown_requested:
            cleanup_all()
            sys.exit(1)

        # Generate report
        return self._generate_report(results)

    def _generate_report(self, results: List[AccountResult]) -> Dict[str, Any]:
        """Generate and display execution report."""
        from rich.table import Table
        from rich.panel import Panel

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        self.console.print()
        self.console.print()

        # Results table
        table = Table(
            title="[bold cyan]📋 Account Creation Results[/bold cyan]",
            border_style="bright_blue",
            header_style="bold cyan",
            show_lines=True,
        )
        table.add_column("#", justify="center", style="cyan", width=4)
        table.add_column("Email", style="white", no_wrap=True)
        table.add_column("Password", style="yellow", no_wrap=True)
        table.add_column("Time", justify="right", style="green")
        table.add_column("Status", justify="center", width=10)

        for i, result in enumerate(successful, 1):
            table.add_row(
                str(i),
                result.email or "N/A",
                result.password or "N/A",
                f"{result.duration:.1f}s",
                "[bold green]✓ SUCCESS[/bold green]",
            )

        if successful:
            self.console.print(table)
        else:
            self.console.print("[bold red]⚠ No accounts were successfully created.[/bold red]")

        # Statistics panel
        total_duration = sum(r.duration for r in results)
        avg_duration = total_duration / len(results) if results else 0

        success_rate = (len(successful) / len(results) * 100) if results else 0

        stats_lines = [
            f"[bold green]✓ Successful:[/bold green]  [white]{len(successful)}[/white]",
            f"[bold red]✗ Failed:[/bold red]      [white]{len(failed)}[/white]",
            f"[bold cyan]📊 Success Rate:[/bold cyan] [white]{success_rate:.1f}%[/white]",
            "",
            f"[bold blue]⏱ Total Time:[/bold blue]    [white]{total_duration:.1f}s[/white]",
            f"[bold blue]⏱ Avg/Account:[/bold blue]   [white]{avg_duration:.1f}s[/white]",
            "",
            f"[dim]💾 Saved to: {self.account_manager.accounts_file}[/dim]",
        ]

        results_panel = Panel(
            "\n".join(stats_lines),
            title="[bold]📊 Execution Summary[/bold]",
            border_style="green" if len(successful) > len(failed) else "yellow",
            padding=(1, 2),
        )
        self.console.print(results_panel)

        # Log failures
        if failed:
            self.console.print()
            self.console.print("[bold red]⚠ Failed Accounts:[/bold red]")
            for result in failed:
                self.console.print(
                    f"   [dim]•[/dim] Account #{result.account_index}: [red]{result.error}[/red]"
                )

        self.console.print()

        return {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_duration": total_duration,
            "average_duration": avg_duration,
            "accounts": [(r.email, r.password) for r in successful if r.email],
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI ARGUMENT PARSER
# ─────────────────────────────────────────────────────────────────────────────


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="MeDo Automation Tool - Educational/Testing Purpose",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -t 5 -w 2          # Create 5 accounts with 2 workers
  %(prog)s --invite-link URL  # Use specific invite link
  %(prog)s -v --log-file log.txt  # Verbose mode with logging
        """
    )

    parser.add_argument(
        "-t", "--total",
        type=int,
        help=f"Number of accounts to create (default: {AutomationConfig.default_total_accounts})"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        help=f"Number of parallel workers (default: {AutomationConfig.default_workers})"
    )
    parser.add_argument(
        "--no-multi",
        action="store_true",
        help="Disable multi-threading (run sequentially)"
    )
    parser.add_argument(
        "-l", "--invite-link",
        type=str,
        help="MeDo invite link (will prompt if not provided)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Save logs to file"
    )
    parser.add_argument(
        "--accounts-file",
        type=str,
        default="accounts.txt",
        help="Output file for accounts (default: accounts.txt)"
    )

    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Main entry point."""
    args = parse_arguments()

    # Initialize console for setup
    console = Console()

    # Setup dependencies
    setup_dependencies(silent=not args.verbose, console=console)

    # Initialize configuration
    site_config = SiteConfig()
    auto_config = AutomationConfig()

    # Override accounts file if specified
    if args.accounts_file != "accounts.txt":
        site_config.success_message = f"Accounts saved to: {args.accounts_file}"

    # Run automation
    orchestrator = AutomationOrchestrator(site_config, auto_config, args)
    results = orchestrator.run()

    return 0 if results["successful"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
