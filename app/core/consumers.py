import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Mobil cihaz veya web paneli bağlandığında bu odaya (gruba) alıyoruz.
        self.room_group_name = 'home_alerts'

        # Gruba katıl
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Bağlantı koptuğunda gruptan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Backend'den bir tehlike sinyali geldiğinde bu fonksiyon tetiklenecek
    async def send_alert(self, event):
        message = event['message']
        alert_type = event['alert_type']
        device_name = event.get('device_name', 'Bilinmeyen Cihaz')
        value = event.get('value', alert_type)
        timestamp = event.get('timestamp', '')

        # Mobil cihaza JSON olarak gönder
        await self.send(text_data=json.dumps({
            'type': 'alert',
            'alert_type': alert_type,
            'message': message,
            'device_name': device_name,
            'value': value,
            'timestamp': timestamp
        }))