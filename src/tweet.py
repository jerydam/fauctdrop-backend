import asyncio
from playwright.async_api import async_playwright
import getpass

async def login_and_save():
    username = getpass.getuser()
    # Use your real profile (same as before)
    user_data_dir = f"/home/{username}/snap/chromium/common/chromium"
    profile_name = "Default"   # ← change if needed (Profile 1, etc.)

    print("Opening your real Chromium profile...")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            executable_path="/snap/bin/chromium",
            args=[
                f"--profile-directory={profile_name}",
                "--no-first-run",
                "--disable-infobars",
            ],
            ignore_default_args=["--enable-automation"],
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://x.com")

        print("\n✅ Browser opened with your real account.")
        print("→ Please make sure you are logged in to X/Twitter")
        print("→ Then come back here and press Enter to save the session...")

        input("\nPress Enter when you are logged in...")

        # Save full storage state (cookies + localStorage + IndexedDB etc.)
        storage = await context.storage_state(path="twitter_storage_state.json")
        print(f"✅ Storage state saved to: twitter_storage_state.json")
        print("You can now delete this script or keep it for future logins.")

        await context.close()

asyncio.run(login_and_save())