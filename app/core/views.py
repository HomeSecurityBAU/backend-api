from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Home, Room, Device, EventLog, AccessLog
from .serializers import HomeSerializer, RoomSerializer, DeviceSerializer, EventLogSerializer, AccessLogSerializer


#EV VIEW
class HomeViewSet(viewsets.ModelViewSet): #ModelViewSet otomatik olarak get, post, put ve delete işlemlerini yapcak
    queryset = Home.objects.all()
    serializer_class = HomeSerializer

#ODA VIEW
class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer

#CİHAZ VIEW
class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

#EVENT LOG VIEW
class EventLogViewSet(viewsets.ModelViewSet):
    queryset = EventLog.objects.all()
    serializer_class = EventLogSerializer

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
            'home_alerts',
            {
                'type': 'send_alert',  # AlertConsumer içerisindeki çalışacak fonksiyon adı
                'alert_type': event_log.value,
                'message': f"{device.name} cihazından '{event_log.value}' uyarısı alındı!",
                'device_name': device.name,
                'value': event_log.value,
                'timestamp': event_log.timestamp.isoformat() # Mobil tarafta parse edilmesi kolay olsun diye ISO 8601 formatı
            }
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

#ACCESS LOG VIEW
class AccessLogViewSet(viewsets.ModelViewSet):
    queryset = AccessLog.objects.all()
    serializer_class = AccessLogSerializer
