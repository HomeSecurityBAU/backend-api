from django.shortcuts import render
from rest_framework import viewsets
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

#ACCESS LOG VIEW
class AccessLogViewSet(viewsets.ModelViewSet):
    queryset = AccessLog.objects.all()
    serializer_class = AccessLogSerializer


