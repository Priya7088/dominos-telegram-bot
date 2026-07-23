"""
Playwright-based Domino's India browser automation (FIXED).
अब बेहतर selectors और debugging के साथ।
"""
import asyncio
import os
import json
import time
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PwTimeout

from config import (
    DOMINOS_BASE_URL,
    DOMINOS_MOBILE_URL,
    PLAYWRIGHT_HEADLESS,
    PLAYWRIGHT_TIMEOUT,
)
from session_store import session_store


# Debug directory for screenshots
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


class DominosBrowser:
    """
    Improved browser automation with better selectors and debugging.
    """

    _instance = None
    _browser: Optional[Browser] = None
    _playwright = None

    @classmethod
    async def get_browser(cls) -> Browser:
        if cls._browser is None or not cls._browser.is_connected():
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(
                headless=PLAYWRIGHT_HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=390,844",
                ],
            )
        return cls._browser

    @classmethod
    async def close_browser(cls):
        if cls._browser:
            await cls._browser.close()
            cls._browser = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None

    @staticmethod
    async def create_context(cookies: list = None) -> BrowserContext:
        browser = await DominosBrowser.get_browser()
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.6478.122 Mobile Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        if cookies:
            await context.add_cookies(cookies)
        return context

    @staticmethod
    async def _take_debug_screenshot(page: Page, name: str):
        """Take a screenshot for debugging purposes."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(DEBUG_DIR, f"{name}_{timestamp}.png")
            await page.screenshot(path=path, full_page=True)
            print(f"📸 Debug screenshot saved: {path}")
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")

    @staticmethod
    async def _get_page_text(page: Page) -> str:
        """Get visible text from page for debugging."""
        try:
            text = await page.inner_text("body")
            return text[:500]
        except Exception:
            return ""

    @staticmethod
    async def _find_input_by_js(page: Page, field_type: str = "phone") -> dict:
        """
        JavaScript fallback: Find input field by label/placeholder text.
        Returns {"found": bool, "selector": str, "method": str}
        """
        if field_type == "phone":
            script = """
            () => {
                // Try multiple approaches to find the phone input
                const selectors = [
                    // By type
                    'input[type="tel"]',
                    // By autocomplete
                    'input[autocomplete="tel"]',
                    'input[autocomplete="tel-national"]',
                    // By inputmode
                    'input[inputmode="numeric"]',
                    'input[inputmode="tel"]',
                    // By name
                    'input[name="mobile"]',
                    'input[name="phone"]',
                    'input[name="telephone"]',
                    'input[name="mobileno"]',
                    'input[name="phoneNumber"]',
                    // By id containing
                    'input[id*="mobile"]',
                    'input[id*="phone"]',
                    'input[id*="tel"]',
                    // By placeholder
                    'input[placeholder*="Mobile"]',
                    'input[placeholder*="Phone"]',
                    'input[placeholder*="phone"]',
                    'input[placeholder*="mobile"]',
                    // By class
                    'input[class*="phone"]',
                    'input[class*="mobile"]',
                    'input[class*="input"]',
                ];
                
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        return { 
                            found: true, 
                            selector: sel,
                            tag: el.tagName,
                            type: el.type,
                            name: el.name,
                            id: el.id,
                            className: el.className,
                            placeholder: el.placeholder,
                            rect: el.getBoundingClientRect()
                        };
                    }
                }
                
                // Last resort: find any visible input
                const allInputs = document.querySelectorAll('input');
                for (const inp of allInputs) {
                    if (inp.offsetParent !== null) { // visible
                        return {
                            found: true,
                            selector: 'any visible input',
                            tag: inp.tagName,
                            type: inp.type,
                            name: inp.name,
                            id: inp.id,
                            className: inp.className,
                            placeholder: inp.placeholder
                        };
                    }
                }
                
                return { found: false, selector: null };
            }
            """
        elif field_type == "otp":
            script = """
            () => {
                const selectors = [
                    'input[autocomplete="one-time-code"]',
                    'input[inputmode="numeric"]',
                    'input[type="text"][inputmode="numeric"]',
                    'input[class*="otp"]',
                    'input[id*="otp"]',
                    'input[name*="otp"]',
                    'input[placeholder*="OTP"]',
                    'input[placeholder*="otp"]',
                    'input[aria-label*="OTP"]',
                    'input[aria-label*="otp"]',
                ];
                
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) {
                        return { 
                            found: true, 
                            selector: sel,
                            tag: el.tagName,
                            type: el.type,
                            name: el.name,
                            id: el.id
                        };
                    }
                }
                
                // Find all visible inputs
                const allInputs = document.querySelectorAll('input');
                for (const inp of allInputs) {
                    if (inp.offsetParent !== null) {
                        return {
                            found: true,
                            selector: 'any visible input',
                            tag: inp.tagName,
                            type: inp.type,
                            name: inp.name,
                            id: inp.id
                        };
                    }
                }
                
                return { found: false, selector: null };
            }
            """
        elif field_type == "button":
            script = """
            (buttonText) => {
                const texts = buttonText || ['Continue', 'Send OTP', 'Login', 'Verify', 
                                              'Submit', 'Next', 'Get OTP', 'Proceed'];
                // Try by text content
                for (const text of texts) {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        if (btn.textContent.trim().toLowerCase().includes(text.toLowerCase())) {
                            return {
                                found: true,
                                method: 'text',
                                text: btn.textContent.trim(),
                                tag: btn.tagName,
                                type: btn.type,
                                className: btn.className
                            };
                        }
                    }
                    // Try input[type=submit]
                    const inputs = document.querySelectorAll('input[type="submit"]');
                    for (const inp of inputs) {
                        if (inp.value.toLowerCase().includes(text.toLowerCase())) {
                            return {
                                found: true,
                                method: 'input-submit',
                                text: inp.value,
                                className: inp.className
                            };
                        }
                    }
                }
                
                // Last resort: any submit button
                const anySubmit = document.querySelector('button[type="submit"]');
                if (anySubmit) {
                    return { found: true, method: 'submit-type', text: anySubmit.textContent.trim() };
                }
                
                // Any visible button
                const allBtns = document.querySelectorAll('button');
                for (const btn of allBtns) {
                    if (btn.offsetParent !== null) {
                        return { found: true, method: 'any-visible', text: btn.textContent.trim() };
                    }
                }
                
                return { found: false };
            }
            """

        try:
            result = await page.evaluate(script)
            return result
        except Exception as e:
            return {"found": False, "error": str(e)}

    # ================== IMPROVED LOGIN FLOW ==================

    @staticmethod
    async def send_otp(phone_number: str) -> dict:
        """
        IMPROVED: Send OTP with better element detection and debugging.
        """
        context = await DominosBrowser.create_context()
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        try:
            print(f"\n🔍 Navigating to Domino's login page...")
            
            # Try multiple URLs for login
            login_urls = [
                f"{DOMINOS_BASE_URL}/postorder-ui/login",
                f"{DOMINOS_MOBILE_URL}/postorder-ui/login",
                f"{DOMINOS_MOBILE_URL}/login",
                f"{DOMINOS_BASE_URL}/login",
            ]

            page_loaded = False
            for url in login_urls:
                try:
                    print(f"  Trying: {url}")
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(3000)
                    page_loaded = True
                    print(f"  ✅ Loaded: {page.url}")
                    break
                except Exception as e:
                    print(f"  ⚠️ Failed: {e}")
                    continue

            if not page_loaded:
                await context.close()
                return {
                    "success": False,
                    "message": "Could not load Domino's login page. Website might be down or blocked.",
                    "page": None,
                    "context": None,
                }

            # Take debug screenshot
            await DominosBrowser._take_debug_screenshot(page, "01_login_page")
            
            # Debug: print page content
            page_text = await DominosBrowser._get_page_text(page)
            print(f"  📄 Page text: {page_text[:300]}")

            # ----- FIND PHONE INPUT FIELD -----
            print("  🔍 Looking for phone input field...")
            phone_input = None
            input_info = None

            # Method 1: JS fallback to find input
            js_result = await DominosBrowser._find_input_by_js(page, "phone")
            print(f"  JS search: {json.dumps(js_result, indent=2, default=str)}")

            if js_result.get("found"):
                sel = js_result["selector"]
                try:
                    phone_input = page.locator(sel).first
                    await phone_input.wait_for(state="visible", timeout=5000)
                    input_info = js_result
                    print(f"  ✅ Found input via JS selector: {sel}")
                except Exception:
                    pass

            # Method 2: Try by label text "Mobile Number"
            if not phone_input:
                try:
                    # Find label with text Mobile/Phone and get associated input
                    label = page.locator("label").filter(has_text=("Mobile")).or_(
                        page.locator("label").filter(has_text=("Phone"))
                    ).or_(
                        page.locator("label").filter(has_text=("mobile"))
                    ).first
                    if await label.is_visible():
                        for_id = await label.get_attribute("for")
                        if for_id:
                            phone_input = page.locator(f"#{for_id}")
                            await phone_input.wait_for(state="visible", timeout=3000)
                            print(f"  ✅ Found input via label for='{for_id}'")
                except Exception:
                    pass

            # Method 3: Look for any input inside a form
            if not phone_input:
                try:
                    # Get all visible inputs
                    all_inputs = await page.locator("input:visible").all()
                    print(f"  Found {len(all_inputs)} visible inputs")
                    for inp in all_inputs[:5]:
                        desc = await inp.get_attribute("placeholder") or \
                               await inp.get_attribute("name") or \
                               await inp.get_attribute("id") or "unknown"
                        print(f"    - input: {desc}")
                    
                    if all_inputs:
                        phone_input = all_inputs[0]
                        print(f"  ✅ Using first visible input")
                except Exception as e:
                    print(f"  ⚠️ Error finding inputs: {e}")

            if not phone_input:
                await DominosBrowser._take_debug_screenshot(page, "02_no_input_found")
                html_content = await page.content()
                with open(os.path.join(DEBUG_DIR, "page_source.html"), "w", encoding="utf-8") as f:
                    f.write(html_content)
                print("  ❌ Could not find phone input. Saved page source for debugging.")
                await context.close()
                return {
                    "success": False,
                    "message": (
                        "Could not find phone number input field on Domino's login page.\n"
                        "यह Domino's वेबसाइट के अपडेट के कारण हो सकता है।\n\n"
                        "Debug info saved. Please try:\n"
                        "1. Bot को restart करें\n"
                        "2. Config में DOMINOS_BASE_URL चेक करें\n"
                        "3. developer se contact करें"
                    ),
                    "page": None,
                    "context": None,
                }

            # ----- ENTER PHONE NUMBER -----
            print(f"  📱 Entering phone: {phone_number}")
            await phone_input.click()
            await page.wait_for_timeout(500)
            await phone_input.fill(phone_number)
            await page.wait_for_timeout(1000)

            # Verify the value was entered
            entered_value = await phone_input.input_value()
            print(f"  ✅ Entered value: '{entered_value}'")

            # ----- FIND AND CLICK SUBMIT BUTTON -----
            print("  🔍 Looking for submit button...")
            submit_button = None

            # Method 1: JS fallback
            js_btn = await DominosBrowser._find_input_by_js(page, "button")
            print(f"  JS button search: {json.dumps(js_btn, indent=2, default=str)}")

            # Method 2: Try by various selectors
            btn_selectors = [
                "button:has-text('Continue')",
                "button:has-text('Send OTP')",
                "button:has-text('Get OTP')",
                "button:has-text('Login')",
                "button:has-text('Next')",
                "button:has-text('Proceed')",
                "button:has-text('Submit')",
                "button[type='submit']",
                "input[type='submit']",
                "button.submit-btn",
                "button.btn-primary",
                "button.btn",
            ]

            for sel in btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        submit_button = btn
                        print(f"  ✅ Found button via: {sel}")
                        break
                except Exception:
                    continue

            # Method 3: Last visible button in form
            if not submit_button and js_btn.get("found"):
                try:
                    # Try clicking using JS
                    await page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            const text = btn.textContent.trim().toLowerCase();
                            if (text.includes('continue') || text.includes('send') || 
                                text.includes('otp') || text.includes('login') ||
                                text.includes('next') || text.includes('submit')) {
                                btn.click();
                                return true;
                            }
                        }
                        // Click any visible button
                        for (const btn of btns) {
                            if (btn.offsetParent !== null) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                    """)
                    print("  ✅ Clicked button via JavaScript")
                    submit_button = "js_clicked"
                except Exception as e:
                    print(f"  ⚠️ JS click failed: {e}")

            if submit_button and submit_button != "js_clicked":
                await submit_button.click()
                print("  ✅ Button clicked!")
            elif not submit_button:
                print("  ⚠️ No button found, trying Enter key")
                await page.keyboard.press("Enter")

            # Wait for OTP to be sent
            await page.wait_for_timeout(5000)

            # ----- CHECK FOR OTP INPUT FIELD -----
            print("  🔍 Checking for OTP input field...")
            
            # Take screenshot
            await DominosBrowser._take_debug_screenshot(page, "03_after_otp_sent")
            
            # Check for OTP input
            otp_js = await DominosBrowser._find_input_by_js(page, "otp")
            print(f"  OTP field search: {json.dumps(otp_js, indent=2, default=str)}")

            otp_found = otp_js.get("found", False)
            
            if otp_found:
                print("  ✅ OTP input field found!")
                return {
                    "success": True,
                    "message": "OTP sent successfully! OTP input field detected.",
                    "page": page,
                    "context": context,
                    "phone": phone_number,
                }
            else:
                # Check URL - if redirected away from login, it might be already logged in
                current_url = page.url
                print(f"  Current URL after submit: {current_url}")
                
                if "login" not in current_url.lower():
                    print("  ✅ Redirected away from login - might be already logged in!")
                    # Login might have happened automatically
                    cookies = await context.cookies()
                    phone = phone_number.replace("91", "") if phone_number.startswith("91") else phone_number
                    session_store.save_session(
                        context.user_data.get("_tg_id", 0) if hasattr(context, 'user_data') else 0,
                        phone, cookies, {}
                    )
                    return {
                        "success": True,
                        "message": "Login successful (auto-redirect detected)!",
                        "page": page,
                        "context": context,
                    }
                
                # Check for error messages
                try:
                    error_text = await page.locator(".error-message, .alert, [role='alert']").first.text_content(timeout=2000)
                    await context.close()
                    return {
                        "success": False,
                        "message": f"Error from website: {error_text}",
                        "page": None,
                        "context": None,
                    }
                except Exception:
                    pass

                # OTP might have been sent but input not detected
                # Return success anyway - user can try entering OTP
                print("  ⚠️ OTP input not found, but continuing...")
                return {
                    "success": True,
                    "message": "OTP request sent. Please check your phone for OTP.",
                    "page": page,
                    "context": context,
                    "phone": phone_number,
                }

        except PwTimeout as e:
            await DominosBrowser._take_debug_screenshot(page, "error_timeout")
            await context.close()
            return {
                "success": False,
                "message": f"Timeout: {str(e)[:200]}",
                "page": None,
                "context": None,
            }
        except Exception as e:
            await DominosBrowser._take_debug_screenshot(page, "error_exception")
            await context.close()
            return {
                "success": False,
                "message": f"Error: {str(e)[:300]}",
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
        IMPROVED: Verify OTP with better element detection.
        """
        try:
            print(f"\n🔐 Verifying OTP: {otp_code}")
            
            # Find OTP input
            otp_input = None
            
            # Method 1: JS fallback
            otp_js = await DominosBrowser._find_input_by_js(page, "otp")
            print(f"  OTP field: {json.dumps(otp_js, indent=2, default=str)}")
            
            if otp_js.get("found"):
                try:
                    otp_input = page.locator(otp_js["selector"]).first
                    await otp_input.wait_for(state="visible", timeout=5000)
                except Exception:
                    otp_input = None

            # Method 2: Find any visible input after login
            if not otp_input:
                try:
                    # After sending OTP, a new input might appear
                    all_inputs = await page.locator("input:visible").all()
                    print(f"  Found {len(all_inputs)} visible inputs for OTP")
                    
                    # Filter for text/tel inputs
                    text_inputs = []
                    for inp in all_inputs:
                        inp_type = await inp.get_attribute("type")
                        if inp_type in (None, "text", "tel", "number", "password"):
                            text_inputs.append(inp)
                    
                    if text_inputs:
                        # Use the first empty text input
                        for inp in text_inputs:
                            val = await inp.input_value()
                            if not val:
                                otp_input = inp
                                break
                        if not otp_input and text_inputs:
                            otp_input = text_inputs[0]
                except Exception as e:
                    print(f"  ⚠️ Error finding OTP input: {e}")

            if not otp_input:
                await DominosBrowser._take_debug_screenshot(page, "04_otp_input_missing")
                await context.close()
                return {
                    "success": False,
                    "message": "Could not find OTP input field. Session may have expired.",
                }

            # Enter OTP
            print(f"  Entering OTP: {otp_code}")
            await otp_input.click()
            await page.wait_for_timeout(300)
            await otp_input.fill(otp_code)
            await page.wait_for_timeout(1500)

            # Verify entered value
            entered = await otp_input.input_value()
            print(f"  Entered value: '{entered}'")

            # Find and click verify button
            print("  Looking for verify button...")
            
            verify_btn = None
            btn_selectors = [
                "button:has-text('Verify')",
                "button:has-text('Login')",
                "button:has-text('Submit')",
                "button:has-text('Continue')",
                "button:has-text('Done')",
                "button:has-text('Confirm')",
                "button[type='submit']",
            ]

            for sel in btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        verify_btn = btn
                        print(f"  ✅ Found verify button: {sel}")
                        break
                except Exception:
                    continue

            if verify_btn:
                await verify_btn.click()
                print("  ✅ Verify button clicked!")
            else:
                # Try JavaScript click
                await page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        const text = btn.textContent.trim().toLowerCase();
                        if (text.includes('verify') || text.includes('login') || 
                            text.includes('submit') || text.includes('done')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
                """)
                print("  ⚠️ No button found, tried JS fallback")

            # Wait for post-login redirect
            await page.wait_for_timeout(5000)
            
            # Take screenshot
            await DominosBrowser._take_debug_screenshot(page, "05_after_verify")
            
            current_url = page.url
            print(f"  URL after verify: {current_url}")

            # Check if login was successful
            if "login" not in current_url.lower() or "otp" not in current_url.lower():
                # SUCCESS!
                cookies = await context.cookies()
                user_info = {}
                
                # Try to get user name
                try:
                    name_el = page.locator("[class*='user'], [class*='profile'], [class*='account']").first
                    if await name_el.is_visible(timeout=2000):
                        user_info["name"] = await name_el.text_content()
                except Exception:
                    pass

                session_store.save_session(telegram_id, phone_number, cookies, user_info)
                print(f"  ✅ Login successful! Cookies saved for {phone_number}")
                
                await context.close()
                return {
                    "success": True,
                    "message": "✅ Login successful! Session saved.",
                }
            else:
                # Check for error on page
                try:
                    err_text = await page.locator("text=invalid, text=wrong, text=error, .error, .alert").first.text_content(timeout=2000)
                    await context.close()
                    return {
                        "success": False,
                        "message": f"Login failed: {err_text}",
                    }
                except Exception:
                    pass

                await context.close()
                return {
                    "success": False,
                    "message": (
                        "OTP verification may have failed. Please try again.\n"
                        "Make sure you entered the correct OTP."
                    ),
                }

        except Exception as e:
            try:
                await context.close()
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Verification error: {str(e)[:200]}",
            }

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
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await page.wait_for_timeout(3000)
            
            is_logged_in = "login" not in page.url.lower()
            return is_logged_in
        except Exception:
            return False
        finally:
            await context.close()

    @staticmethod
    async def get_user_profile(telegram_id: int, phone_number: str) -> dict:
        """Get user profile info from a saved session."""
        cookies = session_store.get_session_cookies(telegram_id, phone_number)
        if not cookies:
            return {}

        context = await DominosBrowser.create_context(cookies)
        page = await context.new_page()
        try:
            await page.goto(
                f"{DOMINOS_BASE_URL}/postorder-ui/",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await page.wait_for_timeout(3000)
            
            # Try to get user info
            info = {}
            try:
                name = await page.locator("[class*='user-name'], [class*='profile-name'], \
                                          [class*='account-name'], [class*='username']").first.text_content(timeout=3000)
                if name:
                    info["name"] = name.strip()
            except Exception:
                pass
            
            return info
        except Exception:
            return {}
        finally:
            await context.close()
