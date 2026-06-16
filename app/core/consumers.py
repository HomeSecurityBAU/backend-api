import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from firebase_admin import messaging
from .models import Home, FCMToken

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        self.home_id = self.scope['url_route']['kwargs']['home_id']
        self.room_group_name = f'home_{self.home_id}_alerts'

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
        is_alarm_active = event.get('is_alarm_active', False)

        # Mobil cihaza JSON olarak gönder
        await self.send(text_data=json.dumps({
            'type': 'alert',
            'alert_type': alert_type,
            'message': message,
            'device_name': device_name,
            'value': value,
            'timestamp': timestamp,
            'is_alarm_active': is_alarm_active
        }))

class CommandConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        self.home_id = self.scope['url_route']['kwargs']['home_id']
        self.room_group_name = f'home_{self.home_id}_commands'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        await self.set_home_online()

    async def disconnect(self, close_code):
        # Bağlantı koptuğunda gruptan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        await self.set_home_offline()
        # Arka planda 30 saniyelik bildirim kontrolü başlat
        asyncio.create_task(self.set_home_offline_with_grace_period(30))

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        msg_type = text_data_json.get('type')
        if msg_type == 'heartbeat':
            await self.update_heartbeat()
        elif msg_type == 'state_update':
            is_armed = text_data_json.get('is_armed')
            alarm_triggered = text_data_json.get('alarm_triggered')
            updated, current_is_armed, current_alarm_triggered = await self.update_home_state(is_armed, alarm_triggered)
            if updated:
                await self.channel_layer.group_send(
                    f'home_{self.home_id}_alerts',
                    {
                        'type': 'send_alert',
                        'alert_type': 'STATE_UPDATE',
                        'message': f"Sistem durumu güncellendi: Armed={current_is_armed}, Alarm={current_alarm_triggered}",
                        'device_name': 'Sistem',
                        'value': 'ARMED' if current_is_armed else 'DISARMED',
                        'timestamp': timezone.now().isoformat(),
                        'is_alarm_active': current_alarm_triggered
                    }
                )

    # View üzerinden 'send_command' eventi tetiklendiğinde çalışır
    async def send_command(self, event):
        # IoT cihazına komutu JSON olarak gönder
        await self.send(text_data=json.dumps({
            'type': 'command',
            **event # Dict unpacking ile command, payload, device_id gibi verileri doğrudan aktarıyoruz
        }))

    @database_sync_to_async
    def set_home_online(self):
        home = Home.objects.filter(id=self.home_id).first()
        if home:
            home.is_online = True
            home.last_heartbeat = timezone.now()
            home.save()

    @database_sync_to_async
    def set_home_offline(self):
        home = Home.objects.filter(id=self.home_id).first()
        if home:
            home.is_online = False
            home.save()

    async def set_home_offline_with_grace_period(self, delay):
        await asyncio.sleep(delay)
        # Gecikme süresi bitince hala çevrimdışı olup olmadığını kontrol et
        still_offline = await self.check_if_still_offline()
        if still_offline:
            await self.notify_home_offline()

    @database_sync_to_async
    def check_if_still_offline(self):
        home = Home.objects.filter(id=self.home_id).first()
        if home:
            # Eğer is_online hala False ise (tekrar bağlanıp is_online = True yapılmadıysa)
            return not home.is_online
        return False

    @database_sync_to_async
    def notify_home_offline(self):
        home = Home.objects.filter(id=self.home_id).first()
        if home:
            owner = home.owner
            if owner:
                tokens = FCMToken.objects.filter(user=owner).values_list('token', flat=True)
                if tokens:
                    message = messaging.MulticastMessage(
                        notification=messaging.Notification(
                            title="Sistem Çevrimdışı!",
                            body="Ev güvenlik sisteminizle bağlantı koptu. Lütfen internet ve güç durumunu kontrol edin."
                        ),
                        tokens=list(tokens),
                    )
                    try:
                        messaging.send_each_for_multicast(message)
                    except Exception as e:
                        print(f"FCM Hata (Offline Bildirimi): {e}")

    @database_sync_to_async
    def update_heartbeat(self):
        home = Home.objects.filter(id=self.home_id).first()
        if home:
            home.last_heartbeat = timezone.now()
            home.save()

    @database_sync_to_async
    def update_home_state(self, is_armed, alarm_triggered):
        home = Home.objects.filter(id=self.home_id).first()
        if home:
            updated = False
            if is_armed is not None and home.is_armed != is_armed:
                home.is_armed = is_armed
                updated = True
            if alarm_triggered is not None and home.alarm_triggered != alarm_triggered:
                home.alarm_triggered = alarm_triggered
                updated = True
            
            if updated:
                home.save()
            return updated, home.is_armed, home.alarm_triggered
        return False, False, False