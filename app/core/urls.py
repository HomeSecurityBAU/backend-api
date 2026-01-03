from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HomeViewSet, RoomViewSet, DeviceViewSet, EventLogViewSet, AccessLogViewSet

#router url leri otomatik oluşturcak (/homes ve /homes/x/ gibi)
router = DefaultRouter()
router.register(r'homes', HomeViewSet)
router.register(r'rooms', RoomViewSet)
router.register(r'devices', DeviceViewSet)
router.register(r'eventlogs', EventLogViewSet)
router.register(r'accesslogs', AccessLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
#bunlar config deki ana url yerine geç.icek