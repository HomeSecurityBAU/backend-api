from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from firebase_admin import messaging
from .models import Home, Room, Device, EventLog, AccessLog, FCMToken
from .serializers import HomeSerializer, RoomSerializer, DeviceSerializer, EventLogSerializer, AccessLogSerializer, FCMTokenSerializer


#EV VIEW
class HomeViewSet(viewsets.ModelViewSet): #ModelViewSet otomatik olarak get, post, put ve delete işlemlerini yapcak
    serializer_class = HomeSerializer

    def get_queryset(self):
        return Home.objects.filter(owner=self.request.user)

#ODA VIEW
class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(home__owner=self.request.user)

#CİHAZ VIEW
class DeviceViewSet(viewsets.ModelViewSet):
    serializer_class = DeviceSerializer

    def get_queryset(self):
        return Device.objects.filter(room__home__owner=self.request.user)

#EVENT LOG VIEW
class EventLogViewSet(viewsets.ModelViewSet):
    serializer_class = EventLogSerializer

    def get_queryset(self):
        return EventLog.objects.filter(device__room__home__owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Veritabanına kaydedilen event log nesnesini ve bağlı olduğu cihazı alıyoruz
        event_log = serializer.instance
        device = event_log.device
        
        # WebSocket için AlertConsumer'a veriyi JSON-uyumlu gönderiyoruz
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'home_{device.room.home.id}_alerts',
            {
                'type': 'send_alert',  # AlertConsumer içerisindeki çalışacak fonksiyon adı
                'alert_type': event_log.value,
                'message': f"{device.name} cihazından '{event_log.value}' uyarısı alındı!",
                'device_name': device.name,
                'value': event_log.value,
                'timestamp': event_log.timestamp.isoformat() # Mobil tarafta parse edilmesi kolay olsun diye ISO 8601 formatı
            }
        )
        
        # FCM ile Push Notification (Bildirim) Gönderimi
        owner = device.room.home.owner
        if owner:
            tokens = FCMToken.objects.filter(user=owner).values_list('token', flat=True)
            if tokens:
                message = messaging.MulticastMessage(
                    notification=messaging.Notification(
                        title="Güvenlik Uyarısı",
                        body=f"{device.name} cihazından '{event_log.value}' uyarısı alındı!"
                    ),
                    tokens=list(tokens),
                )
                try:
                    # Birden fazla cihaza (telefon, tablet vs.) aynı anda göndermek için
                    messaging.send_each_for_multicast(message)
                except Exception as e:
                    print(f"FCM Bildirimi gönderilirken hata oluştu: {e}")

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

#ACCESS LOG VIEW
class AccessLogViewSet(viewsets.ModelViewSet):
    serializer_class = AccessLogSerializer

    def get_queryset(self):
        # Modelle eklediğimiz home yardımıyla access logları sadece ilgili kullanıcı görebilecek
        return AccessLog.objects.filter(home__owner=self.request.user)

# FCM TOKEN VIEW
class FCMTokenViewSet(viewsets.ModelViewSet):
    serializer_class = FCMTokenSerializer

    def get_queryset(self):
        # Giriş yapan kullanıcı sadece kendi tokenlarını görebilir/silebilir
        return FCMToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Token veritabanına kaydedilirken sahibi otomatik olarak bağlanan kullanıcı olur
        serializer.save(user=self.request.user)
