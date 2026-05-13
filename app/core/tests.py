import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter

from .models import Home, Room, Device, EventLog
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
async def test_alert_consumer_connection():
    application = URLRouter(websocket_urlpatterns)
    communicator = WebsocketCommunicator(application, "/ws/alerts/home123/")
    
    # Bağlantıyı kabul etmesini bekliyoruz
    connected, subprotocol = await communicator.connect()
    assert connected is True
    
    await communicator.disconnect()
