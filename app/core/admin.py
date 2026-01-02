from django.contrib import admin
from .models import Home, Room, Device, EventLog, AccessLog

# değişebilir şimdilik böyle kalsın
@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_name', 'created_at')
    search_fields = ('name', 'owner_name')

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'home', 'created_at')
    search_fields = ('name',) 
    list_filter = ('home',)

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'room', 'device_type', 'is_active')
    search_fields = ('name', 'device_type')
    list_filter = ('room', 'device_type', 'is_active')

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ('device', 'value', 'description', 'timestamp')
    list_filter = ('device', 'timestamp')

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'direction', 'timestamp')
    list_filter = ('direction', 'timestamp',)
    search_fields = ('user_id',)