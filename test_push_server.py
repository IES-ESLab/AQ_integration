"""
地震目錄即時推送測試 Server

模擬即時地震事件推送流程：
1. add_event - 初始事件 (含基本定位和 picks)
2. update_location - 更新精確定位（含距離、方位角等）
3. update_focal - 更新震源機制

使用 WebSocket 進行推送，供 web 端測試使用。
"""

import asyncio
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
import argparse

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("請安裝 websockets: pip install websockets")
    exit(1)


class EarthquakePushServer:
    def __init__(self, catalog_path: str, picks_path: str):
        self.catalog = pd.read_csv(catalog_path)
        self.picks = pd.read_csv(picks_path)
        self.clients: set = set()
        self.event_queue: list = []
        self.current_event_idx = 0

        # 預處理事件佇列
        self._prepare_event_queue()

    def _prepare_event_queue(self):
        """準備事件推送佇列"""
        for event in self.catalog.itertuples():
            event_id = int(event.event_index)
            event_picks = self.picks[self.picks['event_index'] == event_id]

            # 階段 1: add_event
            add_event_msg = self._build_add_event(event, event_picks)
            self.event_queue.append(('add_event', add_event_msg))

            # 階段 2: update_location (如果有 h3dd 定位結果)
            if pd.notna(getattr(event, 'h3dd_longitude', None)):
                update_loc_msg = self._build_update_location(event, event_picks)
                self.event_queue.append(('update_location', update_loc_msg))

            # 階段 3: update_focal (如果有震源機制)
            if pd.notna(getattr(event, 'strike', None)):
                update_focal_msg = self._build_update_focal(event)
                self.event_queue.append(('update_focal', update_focal_msg))

        print(f"已準備 {len(self.event_queue)} 個推送訊息 (來自 {len(self.catalog)} 個事件)")

    def _build_add_event(self, event, picks: pd.DataFrame) -> dict:
        """建立 add_event 訊息"""
        pol_map = {
            'x': 'x',
            'D': '-',
            'U': '+',
        }
        associated_picks = {}

        for pick in picks.itertuples():
            station_id = pick.station_id
            phase_type = pick.phase_type

            if station_id not in associated_picks:
                associated_picks[station_id] = {}

            if phase_type == 'P':
                polarity = pick.polarity
                phase_data = {
                    'phase_time': pick.phase_time,
                    'phase_score': pick.phase_score,
                    'polarity': pol_map.get(polarity, 'x')
                }
            else:
                phase_data = {
                    'phase_time': pick.phase_time,
                    'phase_score': pick.phase_score
                }

            associated_picks[station_id][phase_type] = phase_data

        mag = getattr(event, 'magnitude', None)
        return {
            'event_id': int(event.event_index),
            'event_time': event.time,
            'longitude': event.longitude,
            'latitude': event.latitude,
            'depth_km': event.depth_km,
            'magnitude': mag if pd.notna(mag) else None,
            'num_picks': int(event.num_picks),
            'num_p_picks': int(event.num_p_picks),
            'num_s_picks': int(event.num_s_picks),
            'associated_picks': associated_picks
        }

    def _build_update_location(self, event, picks: pd.DataFrame) -> dict:
        """建立 update_location 訊息"""
        associated_picks = {}

        for pick in picks.itertuples():
            station_id = pick.station_id
            phase_type = pick.phase_type

            if station_id not in associated_picks:
                associated_picks[station_id] = {}

            phase_data = {"magnitude": None}  # 預設 magnitude 為 None
            phase_data['distance_km'] = pick.dist
            phase_data['azimuth'] = pick.azimuth
            phase_data['takeoff_angle'] = pick.takeoff_angle
            if pd.notna(pick.magnitude):
                phase_data['magnitude'] = pick.magnitude

            if phase_data:
                associated_picks[station_id][phase_type] = phase_data

        mag = getattr(event, 'magnitude', None)
        return {
            'event_id': int(event.event_index),
            'longitude': event.h3dd_longitude,
            'latitude': event.h3dd_latitude,
            'depth_km': event.h3dd_depth_km,
            'magnitude': mag if pd.notna(mag) else None,
            'associated_picks': associated_picks
        }

    def _build_update_focal(self, event) -> dict:
        """建立 update_focal 訊息"""
        msg = {
            'event_id': int(event.event_index)
        }

        focal_fields = ['strike', 'strike_err', 'dip', 'dip_err',
                        'rake', 'rake_err', 'quality_index', 'num_of_polarity']

        for field in focal_fields:
            value = getattr(event, field, None)
            if field in ['quality_index']:
                msg[field] = float(value)
            else:
                msg[field] = int(value)

        return msg

    async def register(self, websocket):
        """註冊新的 client 連線"""
        self.clients.add(websocket)
        client_info = f"{websocket.remote_address}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 新連線: {client_info} (總連線數: {len(self.clients)})")

        # 發送歡迎訊息
        await websocket.send(json.dumps({
            'type': 'connected',
            'message': '已連線至地震推送測試 Server',
            'total_events': len(self.catalog),
            'total_messages': len(self.event_queue)
        }))

    async def unregister(self, websocket):
        """取消註冊 client"""
        self.clients.discard(websocket)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 連線斷開 (剩餘連線數: {len(self.clients)})")

    async def broadcast(self, message: dict):
        """廣播訊息給所有 clients"""
        if self.clients:
            message_str = json.dumps(message, ensure_ascii=False)
            await asyncio.gather(
                *[client.send(message_str) for client in self.clients],
                return_exceptions=True
            )

    async def handler(self, websocket):
        """處理 WebSocket 連線"""
        await self.register(websocket)
        try:
            async for message in websocket:
                # 處理來自 client 的指令
                try:
                    cmd = json.loads(message)
                    await self.handle_command(websocket, cmd)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': '無效的 JSON 格式'
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def handle_command(self, websocket, cmd: dict):
        """處理 client 指令"""
        action = cmd.get('action')

        if action == 'next':
            # 推送下一個訊息
            await self.push_next()

        elif action == 'push_all':
            # 連續推送所有訊息
            interval = cmd.get('interval', 2.0)
            await self.push_all(interval)

        elif action == 'reset':
            # 重置佇列
            self.current_event_idx = 0
            await websocket.send(json.dumps({
                'type': 'info',
                'message': '佇列已重置'
            }))

        elif action == 'status':
            # 取得目前狀態
            await websocket.send(json.dumps({
                'type': 'status',
                'current_index': self.current_event_idx,
                'total_messages': len(self.event_queue),
                'connected_clients': len(self.clients)
            }))

        elif action == 'list_events':
            # 列出所有事件
            events = []
            for event in self.catalog.itertuples():
                mag = getattr(event, 'magnitude', None)
                events.append({
                    'event_id': int(event.event_index),
                    'time': event.time,
                    'magnitude': round(mag, 1) if pd.notna(mag) else None
                })
            await websocket.send(json.dumps({
                'type': 'event_list',
                'events': events
            }))

        elif action == 'push_event':
            # 推送特定事件的所有訊息
            event_id = cmd.get('event_id')
            await self.push_event(event_id)

        else:
            await websocket.send(json.dumps({
                'type': 'help',
                'commands': {
                    'next': '推送下一個訊息',
                    'push_all': '連續推送所有訊息 (可設定 interval 秒數)',
                    'push_event': '推送特定事件 (需設定 event_id)',
                    'reset': '重置佇列到開頭',
                    'status': '取得目前狀態',
                    'list_events': '列出所有事件'
                }
            }))

    async def push_next(self):
        """推送下一個訊息"""
        if self.current_event_idx >= len(self.event_queue):
            await self.broadcast({
                'type': 'info',
                'message': '所有訊息已推送完畢'
            })
            return

        msg_type, msg_data = self.event_queue[self.current_event_idx]

        payload = {msg_type: msg_data}

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 推送: {msg_type} (event_id: {msg_data['event_id']})")
        await self.broadcast(payload)

        self.current_event_idx += 1

    async def push_all(self, interval: float = 2.0):
        """連續推送所有訊息"""
        while self.current_event_idx < len(self.event_queue):
            await self.push_next()
            await asyncio.sleep(interval)

    async def push_event(self, event_id: int):
        """推送特定事件的所有訊息"""
        event_messages = [
            (msg_type, msg_data)
            for msg_type, msg_data in self.event_queue
            if msg_data['event_id'] == event_id
        ]

        if not event_messages:
            await self.broadcast({
                'type': 'error',
                'message': f'找不到事件 ID: {event_id}'
            })
            return

        for msg_type, msg_data in event_messages:
            payload = {msg_type: msg_data}
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 推送: {msg_type} (event_id: {event_id})")
            await self.broadcast(payload)
            await asyncio.sleep(1.0)  # 每個訊息間隔 1 秒


async def main():
    parser = argparse.ArgumentParser(description='地震目錄即時推送測試 Server')
    parser.add_argument('--host', default='localhost', help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=8765, help='Server port (default: 8765)')
    parser.add_argument('--catalog', default='./example_csv/events.csv',
                        help='Catalog CSV 路徑')
    parser.add_argument('--picks', default='./example_csv/picks.csv',
                        help='Picks CSV 路徑')

    args = parser.parse_args()

    # 檢查檔案是否存在
    catalog_path = Path(args.catalog)
    picks_path = Path(args.picks)

    if not catalog_path.exists():
        print(f"錯誤: 找不到 catalog 檔案: {catalog_path}")
        return

    if not picks_path.exists():
        print(f"錯誤: 找不到 picks 檔案: {picks_path}")
        return

    server = EarthquakePushServer(str(catalog_path), str(picks_path))

    print("=" * 60)
    print("地震目錄即時推送測試 Server")
    print("=" * 60)
    print(f"WebSocket URL: ws://{args.host}:{args.port}")
    print(f"Catalog: {args.catalog} ({len(server.catalog)} 筆事件)")
    print(f"Picks: {args.picks} ({len(server.picks)} 筆震相)")
    print("=" * 60)
    print("等待連線中...")
    print()
    print("Client 可用指令:")
    print('  {"action": "next"}              - 推送下一個訊息')
    print('  {"action": "push_all", "interval": 2}  - 連續推送 (間隔秒數)')
    print('  {"action": "push_event", "event_id": 22015}  - 推送特定事件')
    print('  {"action": "status"}            - 查看狀態')
    print('  {"action": "reset"}             - 重置佇列')
    print("=" * 60)

    async with serve(server.handler, args.host, args.port):
        await asyncio.Future()  # 永久運行


if __name__ == '__main__':
    asyncio.run(main())
