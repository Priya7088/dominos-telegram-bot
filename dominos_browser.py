"""
Playwright-based Domino's India browser automation.
Handles login (OTP), session management, and page interactions.
"""
import asyncio
import time
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import (
    DOMINOS_BASE_URL,
    PLAYWRIGHT_HEADLESS,
    PLAYWRIGHT_TIMEOUT,
)
from session_store import session_store


class DominosBrowser:
    """
    Manages a headless Chromium browser for automating
    Domino's India website interactions.
    """

    _instance = None
    _browser: Optional[Browser] = None

    @classmethod
    async def get_browser(cls) -> Browser:
        if cls._browser is None or not cls._browser.is_connected():
            pw = await async_playwright().start()
            cls._browser = await pw.chromium.launch(
                headless=PLAYWRIGHT_HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
        return cls._browser

    @classmethod
    async def close_browser(cls):
        if cls._browser:
            await cls._browser.close()
            cls._browser = None

    @staticmethod
    async def create_context(cookies: list = None) -> BrowserContext:
        browser = await DominosBrowser.get_browser()
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},  # Mobile viewport
            user_agent=(
                "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.6422.147 Mobile Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        if cookies:
            await context.add_cookies(cookies)
        return context

    # ================== LOGIN FLOW ==================

    @staticmethod
    async def send_otp(phone_number: str) -> dict:
        """
        Step 1: Open Domino's login page, enter phone number,
        click to send OTP. Returns status and any reference ID.
        """
        context = await DominosBrowser.create_context()
        page = await context.new_page()
        try:
            page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

            # Navigate to login page
            await page.goto(
                f"{DOMINOS_BASE_URL}/postorder-ui/login",
                wait_until="networkidle",
            )
            await page.wait_for_timeout(2000)

            # Enter phone number
            # The input field on m.dominos.co.in login page
            phone_input = page.locator("input[type='tel']").or_(
                page.locator("input[placeholder*='Mobile']")
            ).or_(
                page.locator("input.input-phone")
            ).or_(
                page.locator("input[name='mobile']")
            ).first

            await phone_input.wait_for(state="visible", timeout=10000)
            await phone_input.fill(phone_number)
            await page.wait_for_timeout(500)

            # Click the submit/continue button
            submit_btn = page.locator("button[type='submit']").or_(
                page.locator("button:has-text('Continue')")
            ).or_(
                page.locator("button:has-text('Send OTP')")
            ).or_(
                page.locator("button.continue-btn")
            ).first

            await submit_btn.wait_for(state="visible", timeout=5000)
            await submit_btn.click()

            # Wait for OTP to be sent
            await page.wait_for_timeout(3000)

            # Check for OTP input field appearance
            otp_field = page.locator("input[autocomplete='one-time-code']").or_(
                page.locator("input.otp-input")
            ).or_(
                page.locator("input[inputmode='numeric']").first
            )

            try:
                await otp_field.wait_for(state="visible", timeout=15000)
                return {
                    "success": True,
                    "message": "OTP sent successfully!",
                    "page": page,
                    "context": context,
                }
            except Exception:
                # Check if error message is shown
                error_el = page.locator(".error-message").or_(
                    page.locator("text=invalid").or_(
                        page.locator("text=wrong")
                    )
                ).first
                try:
                    error_text = await error_el.text_content(timeout=3000)
                    return {
                        "success": False,
                        "message": f"Error: {error_text}",
                        "page": page,
                        "context": context,
                    }
                except Exception:
                    return {
                        "success": True,
                        "message": "OTP likely sent. Check your phone.",
                        "page": page,
                        "context": context,
                    }

        except Exception as e:
            await context.close()
            return {
                "success": False,
                "message": f"Failed to send OTP: {str(e)}",
                "page": None,
                "context": None,
            }

    @staticmethod
    async def verify_otp(
        page: Page,
        context: BrowserContext,
        otp_code: str,
        telegram_id: int,
        phone_number: str,
    ) -> dict:
        """
        Step 2: Enter OTP code and complete login.
        Saves session cookies on success.
        """
        try:
            # Find OTP input and fill
            otp_field = page.locator("input[autocomplete='one-time-code']").or_(
                page.locator("input.otp-input")
            ).or_(
                page.locator("input[inputmode='numeric']").first
            )

            await otp_field.wait_for(state="visible", timeout=10000)
            await otp_field.fill(otp_code)
            await page.wait_for_timeout(2000)

            # Handle "Verify" or "Login" button
            verify_btn = page.locator("button:has-text('Verify')").or_(
                page.locator("button:has-text('Login')")
            ).or_(
                page.locator("button:has-text('Submit')")
            ).or_(
                page.locator("button[type='submit']")
            ).first

            if await verify_btn.is_visible():
                await verify_btn.click()
                await page.wait_for_timeout(3000)

            # Wait for navigation to home/dashboard after login
            await page.wait_for_url(
                "**/postorder-ui/**",
                timeout=15000,
            )
            await page.wait_for_timeout(2000)

            # Check if login was successful
            # Look for user profile/account elements
            logged_in = await page.locator(
                "text=My Account"
            ).or_(
                page.locator("text=Profile")
            ).or_(
                page.locator(".user-profile")
            ).first.is_visible()

            if logged_in or "login" not in page.url.lower():
                # Login successful! Save cookies
                cookies = await context.cookies()
                # Also try to get user info
                user_info = {}
                try:
                    name_el = page.locator(".user-name").or_(
                        page.locator(".profile-name")
                    ).first
                    user_info["name"] = await name_el.text_content(timeout=3000)
                except Exception:
                    pass

                session_store.save_session(
                    telegram_id, phone_number, cookies, user_info
                )

                return {
                    "success": True,
                    "message": "✓ Login successful! Session saved.",
                }
            else:
                return {
                    "success": False,
                    "message": "Login may have failed. Wrong OTP?",
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"OTP verification failed: {str(e)}",
            }
        finally:
            try:
                await context.close()
            except Exception:
                pass

    # ================== CART OPERATIONS ==================

    @staticmethod
    async def get_cart_url(telegram_id: int, phone_number: str) -> str:
        """
        Get the cart page URL for a logged-in user.
        The bot will return the Domino's cart URL that the WebApp can open.
        """
        cookies = session_store.get_session_cookies(telegram_id, phone_number)
        if not cookies:
            return None

        # Return the cart URL directly - the proxy_server will handle
        # cookie injection
        return f"{DOMINOS_BASE_URL}/postorder-ui/cart"

    @staticmethod
    async def get_account_home_url(telegram_id: int, phone_number: str) -> str:
        """Get the account home/dashboard URL."""
        cookies = session_store.get_session_cookies(telegram_id, phone_number)
        if not cookies:
            return None
        return f"{DOMINOS_BASE_URL}/postorder-ui/"

    @staticmethod
    async def validate_session(telegram_id: int, phone_number: str) -> bool:
        """Check if a saved session is still valid."""
        cookies = session_store.get_session_cookies(telegram_id, phone_number)
        if not cookies:
            return False

        context = await DominosBrowser.create_context(cookies)
        page = await context.new_page()
        try:
            await page.goto(
                f"{DOMINOS_BASE_URL}/postorder-ui/",
                wait_until="networkidle",
                timeout=15000,
            )
            await page.wait_for_timeout(2000)

            # Check if we're logged in
            logged_in = "login" not in page.url.lower()
            return logged_in
        except Exception:
            return False
        finally:
            await context.close()
