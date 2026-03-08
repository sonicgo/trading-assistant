#!/usr/bin/env python3
# Phase 2 minimal scheduler stub.
# External scheduler that loops through portfolios and triggers
# market data refresh via HTTP API calls.

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger, with_correlation

logger = get_logger(__name__)


class Scheduler:
    # Minimal scheduler that refreshes market data for all portfolios.
    
    def __init__(self):
        self.api_base = settings.SCHEDULER_API_BASE_URL
        self.interval_minutes = settings.SCHEDULER_INTERVAL_MINUTES
        self.email = settings.SCHEDULER_AUTH_EMAIL
        self.password = settings.SCHEDULER_AUTH_PASSWORD
        self.access_token: Optional[str] = None
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_event.set()
    
    async def login(self) -> bool:
        # Login to get access token
        if not self.email or not self.password:
            logger.error("Scheduler credentials not configured")
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_base}/api/v1/auth/login",
                    json={"email": self.email, "password": self.password}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    logger.info("Scheduler logged in successfully")
                    return True
                else:
                    logger.error(f"Login failed: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Login error: {e}")
                return False
    
    async def get_portfolios(self) -> list[dict]:
        # Get all portfolios
        if not self.access_token:
            return []
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base}/api/v1/portfolios",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    # Token expired, try re-login
                    if await self.login():
                        return await self.get_portfolios()
                    return []
                else:
                    logger.error(f"Failed to get portfolios: {response.status_code}")
                    return []
            except Exception as e:
                logger.error(f"Error getting portfolios: {e}")
                return []
    
    async def refresh_portfolio(self, portfolio_id: str) -> bool:
        # Trigger market data refresh for a portfolio
        if not self.access_token:
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_base}/api/v1/portfolios/{portfolio_id}/market-data/refresh",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    job_id = data.get("job_id")
                    logger.info(f"Enqueued refresh for portfolio {portfolio_id}, job_id={job_id}")
                    return True
                elif response.status_code == 401:
                    # Token expired, try re-login
                    if await self.login():
                        return await self.refresh_portfolio(portfolio_id)
                    return False
                else:
                    logger.error(f"Failed to refresh portfolio {portfolio_id}: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Error refreshing portfolio {portfolio_id}: {e}")
                return False
    
    async def run(self):
        # Main scheduler loop
        logger.info(f"Scheduler starting (interval={self.interval_minutes}min)...")
        
        # Initial login
        if not await self.login():
            logger.error("Failed to login, scheduler cannot start")
            return
        
        while not self.shutdown_event.is_set():
            start_time = datetime.now(timezone.utc)
            
            # Get all portfolios
            portfolios = await self.get_portfolios()
            logger.info(f"Found {len(portfolios)} portfolios to refresh")
            
            # Refresh each portfolio
            for portfolio in portfolios:
                if self.shutdown_event.is_set():
                    break
                
                portfolio_id = portfolio.get("portfolio_id")
                if portfolio_id:
                    await self.refresh_portfolio(portfolio_id)
            
            # Sleep until next interval
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            sleep_seconds = max(0, self.interval_minutes * 60 - elapsed)
            
            logger.info(f"Sleeping for {sleep_seconds:.0f} seconds...")
            
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=sleep_seconds
                )
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue loop
        
        logger.info("Scheduler shutdown complete")


async def main():
    # Entry point
    scheduler = Scheduler()
    await scheduler.run()


if __name__ == "__main__":
    asyncio.run(main())
