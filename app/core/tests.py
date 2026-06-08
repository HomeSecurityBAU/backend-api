import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter

from .models import Home, Room, Device, EventLog, FCMToken
from core.authentication import KeycloakJWTAuthentication
from .routing import websocket_urlpatterns

# 1. Model Testleri
@pytest.mark.django_db
def test_model_creation_and_relations():
    user = User.objects.create(username="testuser")
    home = Home.objects.create(name="Test Home", owner=user)
    room = Room.objects.create(name="Test Room", home=home)
    device = Device.objects.create(room=room, name="Test Sensor", device_type="SENSOR")
    
    assert home.owner == user
    assert room.home == home
    assert device.room == room
    assert device.name == "Test Sensor"

# 2. API Yetkilendirme Testleri
@pytest.mark.django_db
def test_device_list_unauthenticated():
    client = APIClient()
    # Token/Giriş olmadan cihaz listesine erişim denemesi
    response = client.get('/api/devices/') 
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

# 3. API İşlem Testleri
@pytest.mark.django_db
def test_eventlog_create_authenticated():
    user = User.objects.create(username="testuser")
    home = Home.objects.create(name="Test Home", owner=user)
    room = Room.objects.create(name="Test Room", home=home)
    device = Device.objects.create(room=room, name="Test Sensor", device_type="SENSOR")
    
    client = APIClient()
    client.force_authenticate(user=user)  # Giriş yapmış kullanıcı simülasyonu
    
    payload = {
        "device": device.id,
        "value": "FIRE",
        "description": "Test yangın uyarısı!"
    }
    response = client.post('/api/eventlogs/', data=payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert EventLog.objects.count() == 1
    assert EventLog.objects.first().value == "FIRE"

# 4. WebSocket Testi (Async)
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_alert_consumer_connection():
    from django.contrib.auth.models import User
    user = await User.objects.acreate(username="wsuser")

    application = URLRouter(websocket_urlpatterns)
    communicator = WebsocketCommunicator(application, "/ws/alerts/1/")
    communicator.scope['user'] = user  # Auth bypass: kullanıcıyı scope'a inject et

    connected, subprotocol = await communicator.connect()
    assert connected is True

    await communicator.disconnect()

# 5. Gelişmiş Entegrasyon ve Mantık Testleri (Business Logic & Mocks)
class AdvancedHomeSecurityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser", email="test@test.com")
        self.home = Home.objects.create(name="Test Home", owner=self.user)
        self.room = Room.objects.create(name="Test Room", home=self.home)
        
        self.motion_device = Device.objects.create(room=self.room, name="Motion Sensor", device_type="SENSOR", device_sub_type="MOTION")
        self.smoke_device = Device.objects.create(room=self.room, name="Smoke Sensor", device_type="SENSOR", device_sub_type="SMOKE")
        
        # Test kullanıcısıyla yetkilendir
        self.client.force_authenticate(user=self.user)

    # --- Otonom Alarm Mantığı Testleri ---
    def test_autonomous_alarm_logic_motion_armed(self):
        """Senaryo A: Ev kurulu (is_armed=True) iken 'MOTION' logu geldiğinde alarm tetiklenmeli."""
        self.home.is_armed = True
        self.home.save()
        
        payload = {"device": self.motion_device.id, "value": "MOTION_DETECTED"}
        response = self.client.post('/api/eventlogs/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.home.refresh_from_db()
        self.assertTrue(self.home.alarm_triggered)

    def test_autonomous_alarm_logic_motion_disarmed(self):
        """Senaryo B: Ev kurulu değil (is_armed=False) iken 'MOTION' logu geldiğinde alarm tetiklenmemeli."""
        self.home.is_armed = False
        self.home.save()
        
        payload = {"device": self.motion_device.id, "value": "MOTION_DETECTED"}
        response = self.client.post('/api/eventlogs/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.home.refresh_from_db()
        self.assertFalse(self.home.alarm_triggered)

    def test_autonomous_alarm_logic_smoke(self):
        """Senaryo C: Evin durumuna bakılmaksızın 'SMOKE' cihazından log geldiğinde alarm tetiklenmeli."""
        self.home.is_armed = False # Ev kurulu olmasa bile
        self.home.save()
        
        payload = {"device": self.smoke_device.id, "value": "FIRE_DETECTED"}
        response = self.client.post('/api/eventlogs/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.home.refresh_from_db()
        self.assertTrue(self.home.alarm_triggered)

    # --- WebSocket Komut Testi ---
    @patch('core.views.get_channel_layer')
    def test_send_command_websocket(self, mock_get_channel_layer):
        """send_command uç noktasına istek atıldığında WebSocket üzerinden mesaj gönderildiğini doğrula."""
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        payload = {"command": "START_PUMP"}
        response = self.client.post(f'/api/devices/{self.motion_device.id}/send_command/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_channel_layer.group_send.assert_called_once() # En az bir kere çağrıldı mı?
        
        # Gönderilen komutun detaylarını kontrol et
        args, kwargs = mock_channel_layer.group_send.call_args
        self.assertEqual(args[0], f'home_{self.home.id}_commands')
        self.assertEqual(args[1]['command'], 'START_PUMP')

    # --- FCM Bildirim Testi ---
    @patch('core.views.messaging.send_each_for_multicast')
    def test_fcm_push_notification_on_event(self, mock_fcm_send):
        """Yeni bir EventLog oluştuğunda Firebase bildiriminin tetiklendiğini test et."""
        FCMToken.objects.create(user=self.user, token="dummy_firebase_token_123")
        
        payload = {"device": self.smoke_device.id, "value": "FIRE"}
        response = self.client.post('/api/eventlogs/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_fcm_send.assert_called_once()

    # --- Keycloak / JWT Senkronizasyon Testi ---
    def test_keycloak_jwt_user_synchronization(self):
        """Keycloak JWT payload'u ile gelen kullanıcının yerel Django veritabanında yaratıldığını test et."""
        auth = KeycloakJWTAuthentication()
        
        # JWT'den parse edildiğini varsaydığımız Payload objesi
        validated_token = {
            'preferred_username': 'new_keycloak_user',
            'email': 'new_user@keycloak.local',
            'given_name': 'Genco',
            'family_name': 'Erkal'
        }
        
        # Authentication sınıfındaki get_user metodunu çağır (Senkronizasyon burada oluyor)
        user = auth.get_user(validated_token)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'new_keycloak_user')
        self.assertEqual(user.email, 'new_user@keycloak.local')
        
        # Veritabanından başarılı bir şekilde çekilebildiğini onayla
        db_user = User.objects.get(username='new_keycloak_user')
        self.assertEqual(db_user.username, 'new_keycloak_user')

    # --- Ekstra Güvenlik ve Mantık Testleri ---
    def test_alarm_logic_safe_value(self):
        """Senaryo D: Sensörden güvenli durum ('NORMAL') geldiğinde alarm tetiklenmemeli."""
        self.home.is_armed = True
        self.home.save()
        
        payload = {"device": self.smoke_device.id, "value": "NORMAL"}
        response = self.client.post('/api/eventlogs/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.home.refresh_from_db()
        self.assertFalse(self.home.alarm_triggered)

    def test_nfc_verify_success_for_owner(self):
        """Senaryo E: Kendi evine ait yetkili bir NFC kartı okutulduğunda giriş başarılı olmalı."""
        from .models import NFCTag
        nfc_tag = NFCTag.objects.create(uid="auth_tag_123", user=self.user, home=self.home, is_active=True)
        
        payload = {"uid": "auth_tag_123", "home_id": self.home.id}
        response = self.client.post('/api/verify-nfc/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["authorized"])

    def test_nfc_verify_idor_other_user_tag_rejected(self):
        """Senaryo F: Başka bir kullanıcının evine ait NFC kartı okutulduğunda yetkisiz kart uyarısı dönmeli."""
        from .models import NFCTag
        other_user = User.objects.create(username="otheruser")
        other_home = Home.objects.create(name="Other Home", owner=other_user)
        other_tag = NFCTag.objects.create(uid="other_tag_123", user=other_user, home=other_home, is_active=True)
        
        # İstek atan kendi kullanıcımız (self.user), yetkisiz kartı kendi evi için sorguluyor
        payload = {"uid": "other_tag_123", "home_id": self.home.id}
        response = self.client.post('/api/verify-nfc/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["authorized"])

    def test_nfc_verify_idor_unauthorized_home_alarm_prevented(self):
        """Senaryo G: Yetkisiz bir kart başka bir kullanıcının home_id'si ile okutulduğunda o evde alarm tetiklenmemeli."""
        other_user = User.objects.create(username="otheruser")
        other_home = Home.objects.create(name="Other Home", owner=other_user)
        other_home.is_armed = True
        other_home.save()
        
        # İstek atan kendi kullanıcımız (self.user), yetkisiz kartı baska birinin evi için gönderiyor
        payload = {"uid": "invalid_tag_999", "home_id": other_home.id}
        response = self.client.post('/api/verify-nfc/', data=payload)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Diğer kullanıcının evinde alarm TETİKLENMEMELİDİR (IDOR engellendi)
        other_home.refresh_from_db()
        self.assertFalse(other_home.alarm_triggered)
