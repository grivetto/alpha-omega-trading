#!/usr/bin/env python3
"""
Denaro Auto-Healer v3 - Simplified version with capital checks and alerts
"""
import os, sys, json, time, asyncio, subprocess
from pathlib import Path
from datetime import datetime
from loguru import logger

# Simple notification function - can be enhanced later
async def send_alert(message: str):
    """Send alert - placeholder for actual notification service"""
    logger.info(f"ALERT: {message}")
    # In a real implementation, this would send to Discord/Slack/etc.
    # For now, just log it

async def check_capital_simple():
    """Simple capital check for demonstration"""
    try:
        # Get total balance from portfolio.json
        result = subprocess.run(['cat', '/var/www/html/denaro/portfolio.json'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            trading_usd = data.get('trading_usd', 0)
            logger.info(f"Current trading capital: {trading_usd} USDT")
            
            # Alert if trading capital is too low
            if trading_usd < 20.0:
                await send_alert(f"⚠️ Low trading capital: {trading_usd} USDT")
            return trading_usd
    except Exception as e:
        logger.error(f"Error checking capital: {e}")
    return 0

async def main():
    logger.info("Starting Denaro Auto-Healer v3...")
    
    # Check services
    services_ok = True
    nodes_services = {
        'mc2': ['denaro-mc2', 'denaro-flash-crash'],
        'nuvola': ['denaro-stella', 'denaro-flash-crash'], 
        'marcodg1': ['denaro-marcodg1', 'denaro-flash-crash', 'denaro-pattern-pro']
    }
    
    for node, services in nodes_services.items():
        for service in services:
            try:
                result = subprocess.run(['ssh', '-o', 'ConnectTimeout=5', node, 
                                       'systemctl', 'is-active', service], 
                                      capture_output=True, text=True, timeout=10)
                if result.stdout.strip() != 'active':
                    logger.error(f"Service {service} is DOWN on {node}")
                    await send_alert(f"🚨 Service {service} is DOWN on {node}")
                    services_ok = False
                else:
                    logger.info(f"Service {service} on {node} is ACTIVE")
            except Exception as e:
                logger.error(f"Error checking {service} on {node}: {e}")
    
    # Check capital
    capital = await check_capital_simple()
    
    if services_ok:
        logger.info("All systems OK")
    else:
        logger.warning("Some services have issues")
    
    logger.info("Auto-Healer cycle completed")

if __name__ == "__main__":
    asyncio.run(main())
