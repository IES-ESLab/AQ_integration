"""
地震推送測試 Client

用於測試 WebSocket 推送 Server
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("請安裝 websockets: pip install websockets")
    exit(1)


async def main():
    uri = "ws://localhost:8765"

    print(f"連線至 {uri}...")

    async with websockets.connect(uri) as websocket:
        print("已連線！")
        print()
        print("指令:")
        print("  n / next     - 推送下一個訊息")
        print("  a / all      - 連續推送所有訊息")
        print("  s / status   - 查看狀態")
        print("  r / reset    - 重置佇列")
        print("  l / list     - 列出所有事件")
        print("  e <id>       - 推送特定事件 (例: e 22015)")
        print("  q / quit     - 離開")
        print()

        # 建立接收訊息的 task
        async def receive_messages():
            try:
                async for message in websocket:
                    data = json.loads(message)
                    print()
                    print("=" * 50)
                    print("收到訊息:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    print("=" * 50)
            except websockets.exceptions.ConnectionClosed:
                print("連線已關閉")

        receive_task = asyncio.create_task(receive_messages())

        # 處理使用者輸入
        try:
            while True:
                # 使用 run_in_executor 來非同步讀取 stdin
                loop = asyncio.get_event_loop()
                cmd = await loop.run_in_executor(None, sys.stdin.readline)
                cmd = cmd.strip().lower()

                if not cmd:
                    continue

                if cmd in ('q', 'quit', 'exit'):
                    break
                elif cmd in ('n', 'next'):
                    await websocket.send(json.dumps({'action': 'next'}))
                elif cmd in ('a', 'all'):
                    await websocket.send(json.dumps({'action': 'push_all', 'interval': 2}))
                elif cmd in ('s', 'status'):
                    await websocket.send(json.dumps({'action': 'status'}))
                elif cmd in ('r', 'reset'):
                    await websocket.send(json.dumps({'action': 'reset'}))
                elif cmd in ('l', 'list'):
                    await websocket.send(json.dumps({'action': 'list_events'}))
                elif cmd.startswith('e '):
                    try:
                        event_id = int(cmd.split()[1])
                        await websocket.send(json.dumps({
                            'action': 'push_event',
                            'event_id': event_id
                        }))
                    except (IndexError, ValueError):
                        print("用法: e <event_id>")
                else:
                    await websocket.send(json.dumps({'action': 'help'}))

        finally:
            receive_task.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n離開")
