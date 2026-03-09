"""Entry point: python -m mcp_server"""

import asyncio
import logging

from mcp.server.stdio import stdio_server

from mcp_server.server import server

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
