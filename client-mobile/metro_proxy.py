import asyncio
import sys

LOCAL_PORT = 8081
TARGET_PORT = 8083

async def pipe(reader, writer):
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def handle_client(client_reader, client_writer):
    try:
        target_reader, target_writer = await asyncio.open_connection('127.0.0.1', TARGET_PORT)
    except Exception:
        client_writer.close()
        return
    await asyncio.gather(
        pipe(client_reader, target_writer),
        pipe(target_reader, client_writer),
        return_exceptions=True
    )

async def main():
    server = await asyncio.start_server(handle_client, '0.0.0.0', LOCAL_PORT)
    print(f"Proxy listening on 0.0.0.0:{LOCAL_PORT} -> 127.0.0.1:{TARGET_PORT}", flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
