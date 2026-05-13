from django.db import models
from django.utils import timezone # tarih saat işlemleri için utc formatında evrensel, datetime.datetime.now() kullanınca server saatini alıyo
from django.contrib.auth.models import User

# sonradan değiştirebiliriz örnek olarak oluşturuyorum ben

# EV TABLOSU
class Home(models.Model):
    name = models.CharField(max_length=100, default='My Home')  # oluşturulan evin adı, defaultta My Home
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='homes', null=True)  # User modeli bağlandı
    created_at= models.DateTimeField(auto_now_add=True)
    #floor=models.IntegerField(default=1) # gerek var mı bilemedim, lazımsa kullanırız


    def __str__(self):
        return self.name
    
# ODA TABLOSU
class Room(models.Model):
    name = models.CharField(max_length=50)
    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='rooms')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
# CİHAZ TABLOSU
class Device(models.Model):
    DEVICE_TYPES =(  #buradan emin değilim değiştirilebilir duruma göre
        ('SENSOR', 'Sensor (Input)'), 
        ('ACTUATOR', 'Actuator (Output)'), # vanalar yada alarm gibi şeyler için
    )

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=50)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    is_active = models.BooleanField(default=True)
    #created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.room.name})"
    
# EVENT LOG TABLOSU
class EventLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='logs')
    value= models.CharField(max_length=50)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.device.name} - {self.value} - {self.timestamp}" 
    
# ACCESS LOG TABLOSU
class AccessLog(models.Model): #bura hakkındada çok birşey bilmiyorum parmak izi, yüz tanıma falan eklencek mi? direkt nfc net belirtilmiş ordan gidicem
    DIRECTION_CHOICES=(
        ('IN', 'Giriş'),
        ('OUT', 'Çıkış'),
    )

    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='access_logs', null=True) # Access loglarının kime ait olduğunu bulabilmek için eklendi
    user_id = models.CharField(max_length=50) #kart id
    #gate_id = models.CharField(max_length=50) #ana kapı veya bahçe kapısı gibi olabilir 
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user_id} - {self.direction} - {self.timestamp}" 
    

# FCM TOKEN TABLOSU
class FCMToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:20]}..."


    

    
    


     

    





    
    