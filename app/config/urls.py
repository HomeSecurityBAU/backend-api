"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include #"include" core/urls.py daki router ın oluşturduğu url leri çekebilmek için
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView # spectacular kullanmak için


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),

    #spectacular için url ler lazım olursa diye hepsini koyuyorum
    
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'), #debug için fln kullanılacak url

    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'), # veri göndermek yada çekmek için gerekli formatı görmek için olan url

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),#bu direkt hazır veri tipleri falan için .yaml dosyası indiriyor

]
