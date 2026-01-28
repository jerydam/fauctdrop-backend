import asyncio
import os
from playwright.async_api import async_playwright

async def capture_to_directory():
    # This is the folder the bot will look for
    user_data_dir = "./bot_browser_data"
    
    async with async_playwright() as p:
        print(f"🚀 Launching Chromium to create session in: {user_data_dir}")
        
        # We launch using your local Chromium to inherit the 'human' reputation
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            executable_path="/snap/bin/chromium" # Path for Ubuntu Chromium
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://x.com")

        print("\n📝 LOG IN MANUALLY NOW (2FA, etc.)")
        print("📝 Once you see your feed, come back here and press Enter.")
        
        await asyncio.to_thread(input, "Press Enter to finish and save directory...")
        
        # Everything is automatically saved to the folder as you browse
        await context.close()
        print(f"🎉 SUCCESS! Folder '{user_data_dir}' is ready.")

if __name__ == "__main__":
    asyncio.run(capture_to_directory())