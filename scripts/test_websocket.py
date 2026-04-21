#!/usr/bin/env python3
"""
WebSocket Test Script for SmartLink Service.

Starts the uvicorn server, tests WebSocket connection, and cleans up.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import websockets


# Configuration
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
HEALTH_ENDPOINT = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}/smart-link-service/api/v1/ws/chat/test-client"
API_KEY = "sk-NLiqPXnqoPktCYWXZ2W-kBsdlag0Rs7Gzb3TCv5XGZA"
STARTUP_TIMEOUT = 30  # seconds
HEALTH_CHECK_INTERVAL = 2  # seconds
WS_TIMEOUT = 10  # seconds


def get_server_command() -> list[str]:
    """Get the uvicorn server command."""
    project_root = str(Path(__file__).parent.parent)
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "gateway.main:app",
        "--host",
        SERVER_HOST,
        "--port",
        str(SERVER_PORT),
        "--log-level",
        "warning",
    ], project_root


async def wait_for_server(timeout: int = STARTUP_TIMEOUT) -> bool:
    """Poll health endpoint until server is ready or timeout."""
    import httpx

    print(f"Waiting for server to start (timeout: {timeout}s)...")
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            try:
                response = await client.get(HEALTH_ENDPOINT, timeout=5)
                if response.status_code == 200:
                    print("[OK] Server is ready")
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    print("[FAIL] Server failed to start within timeout")
    return False


async def test_websocket() -> bool:
    """Test WebSocket connection and ping/pong."""
    ws_url = f"{WS_URL}?app_id=app_test&api_key={API_KEY}"
    print(f"Connecting to WebSocket: {ws_url}")

    try:
        async with websockets.connect(
            ws_url,
            open_timeout=WS_TIMEOUT,
        ) as websocket:
            print("[OK] WebSocket connected")

            # Send ping message
            ping_message = {"type": "ping", "data": {}}
            print(f"Sending: {json.dumps(ping_message)}")
            await asyncio.wait_for(
                websocket.send(json.dumps(ping_message)),
                timeout=WS_TIMEOUT,
            )

            # Wait for pong response
            try:
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=WS_TIMEOUT,
                )
                print(f"Received: {response}")

                # Check if response contains pong
                data = json.loads(response)
                if data.get("type", "").lower() == "pong":
                    print("[OK] Pong response received")
                    return True
                else:
                    print("[FAIL] Unexpected response type: {data.get('type')}")
                    return False
            except asyncio.TimeoutError:
                print("[FAIL] Timeout waiting for pong response")
                return False

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"[FAIL] WebSocket connection rejected: HTTP {e.status_code}")
        return False
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[FAIL] Connection closed: {e}")
        return False
    except asyncio.TimeoutError:
        print(f"[FAIL] WebSocket connection timeout ({WS_TIMEOUT}s)")
        return False
    except Exception as e:
        print(f"[FAIL] WebSocket error: {type(e).__name__}: {e}")
        return False


async def run_test() -> int:
    """Run the complete test sequence."""
    import httpx

    server_process = None
    success = False

    try:
        # Start server
        cmd, cwd = get_server_command()
        print(f"Starting server: {' '.join(cmd)}")
        server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
        print(f"Server PID: {server_process.pid}")

        # Wait for server to be ready
        if not await wait_for_server():
            return 1

        # Test WebSocket
        if not await test_websocket():
            return 1

        print("\n[OK] All tests passed!")
        success = True
        return 0

    except KeyboardInterrupt:
        print("\n[FAIL] Test interrupted")
        return 1
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {type(e).__name__}: {e}")
        return 1
    finally:
        # Cleanup server
        if server_process:
            print(f"Stopping server (PID {server_process.pid})...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()
            print("[OK] Server stopped")


def main() -> int:
    """Entry point."""
    print("=" * 60)
    print("SmartLink WebSocket Test")
    print("=" * 60)
    return asyncio.run(run_test())


if __name__ == "__main__":
    sys.exit(main())
