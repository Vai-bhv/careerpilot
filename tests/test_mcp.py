import asyncio
import os
import socket
import subprocess
import sys
import time

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_roundtrip(workspace, monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("CAREERPILOT_API_URL", base)
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                if httpx.get(base + "/health/ready", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("API did not start")

        async def exercise():
            params = StdioServerParameters(
                command=sys.executable, args=["-m", "app.mcp_server"], env=dict(os.environ)
            )
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                toolset = {t.name: t for t in (await session.list_tools()).tools}
                assert toolset["search_jobs"].annotations.readOnlyHint
                assert not toolset["generate_tailored_cv"].annotations.readOnlyHint
                assert "confirm_submission" not in toolset
                result = await session.call_tool(
                    "import_job_description",
                    {
                        "title": "BI Engineer",
                        "company": "Sample",
                        "description": "Requirements: Power BI and DAX.",
                    },
                )
                assert not result.isError
                found = await session.call_tool("search_jobs", {"query": "Sample"})
                assert not found.isError and "BI Engineer" in str(found.content)
                match = await session.call_tool("match_job_to_profile", {"job_id": 1})
                assert not match.isError and "clarify" in str(match.content)

        asyncio.run(exercise())
    finally:
        api.terminate()
        api.wait(timeout=10)
