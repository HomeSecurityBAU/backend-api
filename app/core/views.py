from django.shortcuts import render
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from firebase_admin import messaging
from .models import Home, Room, Device, EventLog, AccessLog, FCMToken, NFCTag
from .serializers import HomeSerializer, RoomSerializer, DeviceSerializer, EventLogSerializer, AccessLogSerializer, FCMTokenSerializer, NFCTagSerializer


#EV VIEW
class HomeViewSet(viewsets.ModelViewSet): #ModelViewSet otomatik olarak get, post, put ve delete işlemlerini yapcak
    serializer_class = HomeSerializer

    def get_queryset(self):
        return Home.objects.filter(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def set_security_mode(self, request, pk=None):
        home = self.get_object()
        arm = request.data.get('arm')

        if arm is None:
            return Response({'error': "'arm' (boolean) parametresi gereklidir."}, status=status.HTTP_400_BAD_REQUEST)

        if arm:
            home.is_armed = True
        else:
            home.is_armed = False
            home.alarm_triggered = False
            
        home.save()
        
        # Pi panel durumunu güncellemek için WebSocket komutu gönder
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'home_{home.id}_commands',
            {
                'type': 'send_command',
                'command': 'SET_SECURITY_MODE',
                'payload': {'is_armed': home.is_armed}
            }
        )

        serializer = self.get_serializer(home)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def authenticate_entry(self, request, pk=None):
        home = self.get_object()
        # pin = request.data.get('pin') # İleride detaylı pin doğrulaması eklenebilir
        
        home.alarm_triggered = False
        home.save()
        
        # Alarmı susturmak için Raspberry Pi'ye WebSocket komutu gönder
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'home_{home.id}_commands',
            {
                'type': 'send_command',
                'command': 'ALARM_STOP',
                'payload': {'message': 'Alarm durduruldu (Mobil Uygulama)'}
            }
        )
        
        return Response({'status': 'Alarm durduruldu ve sistem normale döndü.', 'is_alarm_active': home.alarm_triggered}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def start_nfc_enroll(self, request, pk=None):
        home = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({'error': "'user_id' parametresi gereklidir."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Pi'ye WebSocket üzerinden kayıt modunu başlat komutu gönder
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'home_{home.id}_commands',
            {
                'type': 'send_command',
                'command': 'START_NFC_ENROLL',
                'payload': {'user_id': user_id}
            }
        )
        
        return Response({'status': 'NFC tanımlama modu başlatıldı.', 'user_id': user_id}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        home = self.get_object()
        
        # Odalar (ve cihazlar - RoomSerializer'ın cihazları içerdiği varsayılmaktadır)
        rooms = Room.objects.filter(home=home)
        rooms_data = RoomSerializer(rooms, many=True).data
        
        # Son Olaylar: Cihazlardan gelen en son 10 adet EventLog (Azalan sırada)
        recent_events = EventLog.objects.filter(device__room__home=home).order_by('-timestamp')[:10]
        recent_events_data = EventLogSerializer(recent_events, many=True).data
        
        # Son Girişler: Eve ait en son 5 adet AccessLog (Azalan sırada)
        recent_access = AccessLog.objects.filter(home=home).order_by('-timestamp')[:5]
        recent_access_data = AccessLogSerializer(recent_access, many=True).data
        
        return Response({
            "home": {
                "id": home.id,
                "name": home.name,
                "is_armed": home.is_armed,
                "alarm_triggered": home.alarm_triggered
            },
            "rooms": rooms_data,
            "recent_events": recent_events_data,
            "recent_access": recent_access_data
        }, status=status.HTTP_200_OK)

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

    @action(detail=True, methods=['post'])
    def send_command(self, request, pk=None):
        device = self.get_object()
        command = request.data.get('command')
        payload = request.data.get('payload', {})
        
        if not command:
            return Response({'error': 'Komut (command) parametresi gereklidir.'}, status=status.HTTP_400_BAD_REQUEST)
            
        home_id = device.room.home.id
        
        # WebSocket ile IoT cihazlarına komutu gönder
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'home_{home_id}_commands',
            {
                'type': 'send_command', # Consumer'daki metodun adı
                'command': command,
                'payload': payload,
                'device_id': device.id,
                'device_name': device.name
            }
        )
        
        return Response({'status': 'Komut iletildi'}, status=status.HTTP_200_OK)

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
        home = device.room.home
        
        # Otonom Karar Mekanizması
        # Sadece tehlike veya anormal bir durum belirten değerlerde alarmı tetikliyoruz
        # (NORMAL, OK, CLEAR, CLOSED, SAFE gibi güvenli durum bildirimleri alarm tetiklemez)
        is_danger = event_log.value.upper() not in ['NORMAL', 'OK', 'CLEAR', 'CLOSED', 'SAFE']
        
        if is_danger:
            if device.device_sub_type in ['SMOKE', 'GAS', 'WATER', 'VIBRATION']:
                home.alarm_triggered = True
            elif device.device_sub_type in ['MOTION', 'MAGNETIC']:
                if home.is_armed:
                    home.alarm_triggered = True

            home.save()

        # Alarm tetiklendiyse Raspberry Pi'ye actuator komutu gönder
        channel_layer = get_channel_layer()
        if home.alarm_triggered and is_danger:
            if device.device_sub_type == 'WATER':
                async_to_sync(channel_layer.group_send)(
                    f'home_{home.id}_commands',
                    {'type': 'send_command', 'command': 'ACTIVATE_PUMP', 'payload': {}}
                )
            async_to_sync(channel_layer.group_send)(
                f'home_{home.id}_commands',
                {'type': 'send_command', 'command': 'ACTIVATE_BUZZER', 'payload': {}}
            )

        # WebSocket için AlertConsumer'a veriyi JSON-uyumlu gönderiyoruz
        async_to_sync(channel_layer.group_send)(
            f'home_{home.id}_alerts',
            {
                'type': 'send_alert',  # AlertConsumer içerisindeki çalışacak fonksiyon adı
                'alert_type': event_log.value,
                'message': f"{device.name} cihazından '{event_log.value}' uyarısı alındı!",
                'device_name': device.name,
                'value': event_log.value,
                'timestamp': event_log.timestamp.isoformat(), # Mobil tarafta parse edilmesi kolay olsun diye ISO 8601 formatı
                'is_alarm_active': home.alarm_triggered
            }
        )
        
        # FCM ile Push Notification (Bildirim) Gönderimi
        owner = home.owner
        if owner:
            tokens = FCMToken.objects.filter(user=owner).values_list('token', flat=True)
            if tokens:
                message = messaging.MulticastMessage(
                    notification=messaging.Notification(
                        title="Güvenlik Uyarısı",
                        body=f"{device.name} cihazından '{event_log.value}' uyarısı alındı!"
                    ),
                    data={
                        'is_alarm_active': str(home.alarm_triggered).lower() # FCM data payload sadece string kabul eder
                    },
                    tokens=list(tokens),
                )
                try:
                    # Birden fazla cihaza (telefon, tablet vs.) aynı anda göndermek için
                    messaging.send_each_for_multicast(message)
                except Exception as e:
                    print(f"FCM Bildirimi gönderilirken hata oluştu: {e}")

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        if not isinstance(request.data, list):
            return Response({'error': 'Toplu kayıt işlemi için veri bir liste olmalıdır.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        created_logs = serializer.instance
        channel_layer = get_channel_layer()

        homes_to_update = {}
        water_leak_detected_by_home = {}
        alarm_triggered_by_home = {}
        triggered_devices_by_home = {}

        for event_log in created_logs:
            device = event_log.device
            home = device.room.home
            home_id = home.id

            if home_id not in homes_to_update:
                homes_to_update[home_id] = home
                water_leak_detected_by_home[home_id] = False
                alarm_triggered_by_home[home_id] = False
                triggered_devices_by_home[home_id] = []

            is_danger = event_log.value.upper() not in ['NORMAL', 'OK', 'CLEAR', 'CLOSED', 'SAFE']

            if is_danger:
                if device.device_sub_type in ['SMOKE', 'GAS', 'WATER', 'VIBRATION']:
                    home.alarm_triggered = True
                    alarm_triggered_by_home[home_id] = True
                    triggered_devices_by_home[home_id].append(device.name)
                    if device.device_sub_type == 'WATER':
                        water_leak_detected_by_home[home_id] = True
                elif device.device_sub_type in ['MOTION', 'MAGNETIC']:
                    if home.is_armed:
                        home.alarm_triggered = True
                        alarm_triggered_by_home[home_id] = True
                        triggered_devices_by_home[home_id].append(device.name)

            # WebSocket Bildirimi (Orijinal logun zaman damgasıyla)
            async_to_sync(channel_layer.group_send)(
                f'home_{home.id}_alerts',
                {
                    'type': 'send_alert',
                    'alert_type': event_log.value,
                    'message': f"{device.name} cihazından '{event_log.value}' uyarısı alındı! (Çevrimdışı Senkronizasyon)",
                    'device_name': device.name,
                    'value': event_log.value,
                    'timestamp': event_log.timestamp.isoformat(), 
                    'is_alarm_active': home.alarm_triggered
                }
            )

        # Değişen evleri bir kere kaydet ve aktüatör/FCM bildirimlerini gruplayarak gönder
        for home_id, home in homes_to_update.items():
            if alarm_triggered_by_home[home_id]:
                home.save()

                if water_leak_detected_by_home[home_id]:
                    async_to_sync(channel_layer.group_send)(
                        f'home_{home.id}_commands',
                        {'type': 'send_command', 'command': 'ACTIVATE_PUMP', 'payload': {}}
                    )
                async_to_sync(channel_layer.group_send)(
                    f'home_{home.id}_commands',
                    {'type': 'send_command', 'command': 'ACTIVATE_BUZZER', 'payload': {}}
                )

                # FCM Bildirimi (Tek bir birleştirilmiş mesaj)
                owner = home.owner
                if owner:
                    tokens = FCMToken.objects.filter(user=owner).values_list('token', flat=True)
                    if tokens:
                        devices_list = list(set(triggered_devices_by_home[home_id]))
                        devices_str = ", ".join(devices_list)
                        message = messaging.MulticastMessage(
                            notification=messaging.Notification(
                                title="Güvenlik Uyarısı (Geçmiş Senkronizasyon)",
                                body=f"Sistem çevrimdışı iken şu cihazlardan tehlike tespiti alındı: {devices_str}!"
                            ),
                            data={
                                'is_alarm_active': str(home.alarm_triggered).lower()
                            },
                            tokens=list(tokens),
                        )
                        try:
                            messaging.send_each_for_multicast(message)
                        except Exception as e:
                            print(f"FCM Bildirimi gönderilirken hata oluştu: {e}")

        return Response({'status': f'{len(created_logs)} adet event log başarıyla senkronize edildi.'}, status=status.HTTP_201_CREATED)

#ACCESS LOG VIEW
class AccessLogViewSet(viewsets.ModelViewSet):
    serializer_class = AccessLogSerializer

    def get_queryset(self):
        # Modelle eklediğimiz home yardımıyla access logları sadece ilgili kullanıcı görebilecek
        return AccessLog.objects.filter(home__owner=self.request.user)

    def perform_create(self, serializer):
        access_log = serializer.save()
        if access_log.direction == 'IN':
            home = access_log.home
            if home and (home.is_armed or home.alarm_triggered):
                home.is_armed = False
                home.alarm_triggered = False
                home.save()

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        # Gelen verinin liste olup olmadığını kontrol et
        if not isinstance(request.data, list):
            return Response({'error': 'Toplu kayıt işlemi için veri bir liste olmalıdır.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({'status': f'{len(serializer.instance)} adet access log başarıyla senkronize edildi.'}, status=status.HTTP_201_CREATED)

# FCM TOKEN VIEW
class FCMTokenViewSet(viewsets.ModelViewSet):
    serializer_class = FCMTokenSerializer

    def get_queryset(self):
        # Giriş yapan kullanıcı sadece kendi tokenlarını görebilir/silebilir
        return FCMToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Token veritabanına kaydedilirken sahibi otomatik olarak bağlanan kullanıcı olur
        serializer.save(user=self.request.user)

# NFC TAG VIEW
class NFCTagViewSet(viewsets.ModelViewSet):
    serializer_class = NFCTagSerializer

    def get_queryset(self):
        return NFCTag.objects.filter(home__owner=self.request.user)

    def perform_create(self, serializer):
        tag = serializer.save()
        # Kayıt başarılı uyarısını WebSocket üzerinden yayınla
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'home_{tag.home.id}_alerts',
            {
                'type': 'send_alert',
                'alert_type': 'NFC_ENROLLED',
                'message': f"Yeni NFC kart '{tag.uid}' kullanıcısı '{tag.user.username}' için başarıyla tanımlandı!",
                'device_name': 'NFC Modülü',
                'value': tag.uid,
                'timestamp': timezone.now().isoformat(),
                'is_alarm_active': tag.home.alarm_triggered
            }
        )

# NFC DOĞRULAMA VIEW
class NFCVerifyView(APIView):
    def post(self, request):
        uid = request.data.get('uid')
        home_id = request.data.get('home_id') # Hangi evden istek geldiğini bilmek için Raspberry Pi'nin bu id'yi de payload'a eklemesi gerekir
        
        # Sadece istek atan kullanıcının sahip olduğu evle ilişkili aktif tagleri kontrol et
        tag = NFCTag.objects.filter(uid=uid, is_active=True, home__owner=request.user).first()
        
        if tag:
            # Durumu veri tabanında disarm et
            home = tag.home
            siren_was_active = home.alarm_triggered
            home.is_armed = False
            home.alarm_triggered = False
            home.save()

            # Siren durumu değiştiyse bunu EventLog olarak kaydet
            if siren_was_active:
                buzzer_device = Device.objects.filter(room__home=home, device_sub_type='BUZZER').first()
                if buzzer_device:
                    EventLog.objects.create(
                        device=buzzer_device,
                        value='NORMAL',
                        description='Siren susturuldu (NFC Kart Girişi)'
                    )

            AccessLog.objects.create(
                home=home,
                user_id=tag.uid,
                direction='IN'
            )
            
            # Kart geçerliyse kapıyı açmak için Raspberry Pi'ye WebSocket komutu gönder
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'home_{home.id}_commands',
                {
                    'type': 'send_command',
                    'command': 'OPEN_DOOR',
                    'payload': {'user': tag.user.username}
                }
            )
            
            return Response({
                "authorized": True,
                "message": "Giriş Başarılı",
                "user": tag.user.username
            }, status=status.HTTP_200_OK)
            
        # Kart geçersizse
        if home_id:
            # IDOR zafiyetini engellemek için sadece istek atan kullanıcının kendi evini buluyoruz
            home = Home.objects.filter(id=home_id, owner=request.user).first()
            if home:
                AccessLog.objects.create(
                    home=home,
                    user_id=uid if uid else 'Bilinmeyen',
                    direction='ERR'
                )
            # Ev "Kilitli (Armed)" durumdaysa alarmı tetikle ve bildirim at
            if home and home.is_armed:
                home.alarm_triggered = True
                home.save()
                
                # WebSocket Alert Gönderimi
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'home_{home.id}_alerts',
                    {
                        'type': 'send_alert',
                        'alert_type': 'UNAUTHORIZED_NFC',
                        'message': "İzinsiz NFC kart okutma denemesi!",
                        'device_name': 'NFC Modülü',
                        'value': uid,
                        'timestamp': timezone.now().isoformat(),
                        'is_alarm_active': home.alarm_triggered
                    }
                )
                
                # FCM Push Notification Gönderimi
                owner = home.owner
                if owner:
                    tokens = FCMToken.objects.filter(user=owner).values_list('token', flat=True)
                    if tokens:
                        message = messaging.MulticastMessage(
                            notification=messaging.Notification(
                                title="Güvenlik Uyarısı!",
                                body="Ev kurulu sistemdeyken yetkisiz bir NFC kartı okutuldu!"
                            ),
                            data={'is_alarm_active': 'true'},
                            tokens=list(tokens),
                        )
                        try:
                            messaging.send_each_for_multicast(message)
                        except Exception as e:
                            print(f"FCM Hata: {e}")

        return Response({
            "authorized": False,
            "message": "Geçersiz veya yetkisiz kart"
        }, status=status.HTTP_403_FORBIDDEN)


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
