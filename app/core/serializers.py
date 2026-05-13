from rest_framework import serializers
from .models import Home, Room, Device, EventLog, AccessLog, FCMToken

#Python verisini JSON a çevirmek için 
#EV SERIALIZER
class HomeSerializer(serializers.ModelSerializer): 
    class Meta:
        model = Home
        fields = ['id', 'name', 'owner', 'created_at', 'is_armed', 'alarm_triggered']

#ODA SERIALIZER
class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

#CİHAZ SERIALIZER
class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'room', 'name', 'device_type', 'device_sub_type', 'is_active']

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

# FCM TOKEN SERIALIZER
class FCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ['id', 'token', 'created_at']
