
import requests
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Configuration
API_BASE_URL = os.getenv('ANALYTICS_API_URL', 'http://localhost:10000')
MAX_WAIT_TIME = 600  # 10 minutes max wait for update completion
POLL_INTERVAL = 10   # Check status every 10 seconds

# Logging
def log(message: str, level: str = "INFO"):
    """Simple logging function"""
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] {level}: {message}")

def notify_webhook(webhook_url: str, message: str, success: bool = True):
    """Send notification to webhook (e.g., Slack, Discord)"""
    if not webhook_url:
        return
    
    try:
        payload = {
            "text": f"{'✅' if success else '❌'} Analytics Update: {message}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        
    except Exception as e:
        log(f"Failed to send webhook notification: {str(e)}", "ERROR")

def check_api_health() -> bool:
    """Check if the API is accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        return response.status_code == 200
    except Exception as e:
        log(f"API health check failed: {str(e)}", "ERROR")
        return False

def get_current_status() -> Dict[str, Any]:
    """Get current analytics status"""
    try:
        response = requests.get(f"{API_BASE_URL}/analytics/status", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log(f"Failed to get analytics status: {str(e)}", "ERROR")
        return {"success": False, "error": str(e)}

def trigger_update() -> Dict[str, Any]:
    """Trigger analytics data update"""
    try:
        response = requests.post(f"{API_BASE_URL}/analytics/update", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log(f"Failed to trigger analytics update: {str(e)}", "ERROR")
        return {"success": False, "error": str(e)}

def wait_for_completion() -> Dict[str, Any]:
    """Wait for update to complete and return final status"""
    start_time = time.time()
    
    while time.time() - start_time < MAX_WAIT_TIME:
        try:
            status_response = get_current_status()
            
            if not status_response.get("success"):
                log("Failed to get status during wait", "ERROR")
                time.sleep(POLL_INTERVAL)
                continue
            
            status = status_response.get("status", {})
            
            # Check if update is complete
            if not status.get("updating", False):
                if status.get("completed_at"):
                    log("Update completed successfully")
                    return {
                        "success": True,
                        "completed": True,
                        "duration": status.get("duration_seconds"),
                        "completed_at": status.get("completed_at")
                    }
                elif status.get("failed_at"):
                    log(f"Update failed: {status.get('error', 'Unknown error')}", "ERROR")
                    return {
                        "success": False,
                        "completed": True,
                        "error": status.get("error"),
                        "failed_at": status.get("failed_at")
                    }
            else:
                log(f"Update in progress: {status.get('message', 'Updating...')}")
            
        except Exception as e:
            log(f"Error while waiting for completion: {str(e)}", "ERROR")
        
        time.sleep(POLL_INTERVAL)
    
    log("Update did not complete within timeout", "ERROR")
    return {
        "success": False,
        "completed": False,
        "error": "Timeout waiting for update completion"
    }

def get_dashboard_stats() -> Dict[str, Any]:
    """Get current dashboard statistics"""
    try:
        response = requests.get(f"{API_BASE_URL}/analytics/dashboard", timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success") and result.get("data"):
            return result["data"]
        else:
            return {}
            
    except Exception as e:
        log(f"Failed to get dashboard stats: {str(e)}", "ERROR")
        return {}

def main():
    """Main update process"""
    start_time = datetime.now()
    webhook_url = os.getenv('ANALYTICS_WEBHOOK_URL')  # Optional webhook for notifications
    
    log("Starting analytics auto-update process")
    
    # Check API health
    if not check_api_health():
        error_msg = "API is not accessible"
        log(error_msg, "ERROR")
        notify_webhook(webhook_url, error_msg, False)
        sys.exit(1)
    
    # Get current status
    current_status = get_current_status()
    if not current_status.get("success"):
        error_msg = f"Failed to get current status: {current_status.get('error', 'Unknown error')}"
        log(error_msg, "ERROR")
        notify_webhook(webhook_url, error_msg, False)
        sys.exit(1)
    
    # Check if already updating
    if current_status.get("status", {}).get("updating", False):
        log("Update already in progress, waiting for completion...")
        result = wait_for_completion()
    else:
        # Trigger new update
        log("Triggering analytics data update...")
        update_response = trigger_update()
        
        if not update_response.get("success"):
            error_msg = f"Failed to trigger update: {update_response.get('message', 'Unknown error')}"
            log(error_msg, "ERROR")
            notify_webhook(webhook_url, error_msg, False)
            sys.exit(1)
        
        log("Update triggered successfully, waiting for completion...")
        result = wait_for_completion()
    
    # Process results
    if result.get("success") and result.get("completed"):
        # Get final statistics
        stats = get_dashboard_stats()
        
        duration = result.get("duration", 0)
        total_time = (datetime.now() - start_time).total_seconds()
        
        success_msg = f"Update completed in {duration:.1f}s (total: {total_time:.1f}s)"
        if stats:
            success_msg += f" | Transactions: {stats.get('totalTransactions', 0):,}"
            success_msg += f" | Faucets: {stats.get('totalFaucets', 0):,}"
            success_msg += f" | Claims: {stats.get('totalClaims', 0):,}"
            success_msg += f" | Users: {stats.get('uniqueUsers', 0):,}"
        
        log(success_msg)
        notify_webhook(webhook_url, success_msg, True)
        
    else:
        error_msg = f"Update failed: {result.get('error', 'Unknown error')}"
        log(error_msg, "ERROR")
        notify_webhook(webhook_url, error_msg, False)
        sys.exit(1)
    
    log("Analytics auto-update completed successfully")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Update process interrupted by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log(error_msg, "ERROR")
        webhook_url = os.getenv('ANALYTICS_WEBHOOK_URL')
        notify_webhook(webhook_url, error_msg, False)
        sys.exit(1)