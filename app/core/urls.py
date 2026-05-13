from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HomeViewSet, RoomViewSet, DeviceViewSet, EventLogViewSet, AccessLogViewSet, FCMTokenViewSet

#router url leri otomatik oluşturcak (/homes ve /homes/x/ gibi)
router = DefaultRouter()
router.register(r'homes', HomeViewSet, basename='home')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'eventlogs', EventLogViewSet, basename='eventlog')
router.register(r'accesslogs', AccessLogViewSet, basename='accesslog')
router.register(r'fcmtokens', FCMTokenViewSet, basename='fcmtoken')

urlpatterns = [
    path('', include(router.urls)),
]
#bunlar config deki ana url yerine geç.icek