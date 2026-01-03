from rest_framework import serializers
from .models import Home, Room, Device, EventLog, AccessLog

#Python verisini JSON a çevirmek için 
#EV SERIALIZER
class HomeSerializer(serializers.ModelSerializer): 
    class Meta:
        model = Home
        fields = '__all__'

#ODA SERIALIZER
class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

#CİHAZ SERIALIZER
class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'

#EVENT LOG SERIALIZER
class EventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLog
        fields = '__all__'

#ACCESS LOG SERIALIZER
class AccessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessLog
        fields = '__all__'
