from rest_framework import serializers
from .models import Home, Room, Device, EventLog, AccessLog, FCMToken, NFCTag

#Python verisini JSON a çevirmek için 
#EV SERIALIZER
class HomeSerializer(serializers.ModelSerializer): 
    class Meta:
        model = Home
        fields = ['id', 'name', 'owner', 'created_at', 'is_armed', 'alarm_triggered', 'is_online', 'last_heartbeat']

#ODA SERIALIZER
class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

#CİHAZ SERIALIZER
class DeviceSerializer(serializers.ModelSerializer):
    latest_value = serializers.SerializerMethodField()
    latest_timestamp = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ['id', 'room', 'name', 'device_type', 'device_sub_type', 'is_active', 'latest_value', 'latest_timestamp']

    def get_latest_value(self, obj):
        latest_log = obj.logs.order_by('-timestamp').first()
        if latest_log:
            return latest_log.value
        # Default fallback values depending on sub type
        if obj.device_sub_type == 'MOTION':
            return 'NORMAL'
        elif obj.device_sub_type in ['SMOKE', 'GAS']:
            return 'NORMAL'
        elif obj.device_sub_type == 'WATER':
            return 'NORMAL'
        elif obj.device_sub_type == 'MAGNETIC':
            return 'CLOSED'
        elif obj.device_sub_type == 'NFC':
            return 'LOCKED'
        return 'NORMAL'

    def get_latest_timestamp(self, obj):
        latest_log = obj.logs.order_by('-timestamp').first()
        return latest_log.timestamp.isoformat() if latest_log else None

#EVENT LOG SERIALIZER
class EventLogSerializer(serializers.ModelSerializer):
    device_name = serializers.ReadOnlyField(source='device.name')
    room_name = serializers.ReadOnlyField(source='device.room.name')

    class Meta:
        model = EventLog
        fields = ['id', 'device', 'device_name', 'room_name', 'value', 'description', 'timestamp']

#ACCESS LOG SERIALIZER
class AccessLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AccessLog
        fields = ['id', 'home', 'user_id', 'user_name', 'direction', 'timestamp']

    def get_user_name(self, obj):
        tag = NFCTag.objects.filter(uid=obj.user_id).first()
        if tag and tag.user:
            # First name and last name if available, otherwise username
            if tag.user.first_name:
                return f"{tag.user.first_name} {tag.user.last_name}".strip()
            return tag.user.username
        return 'Yetkisiz Kart'

# FCM TOKEN SERIALIZER
class FCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ['id', 'token', 'created_at']

# NFC TAG SERIALIZER
class NFCTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = NFCTag
        fields = '__all__'
