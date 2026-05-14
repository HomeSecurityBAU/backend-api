from django.db import models
from django.utils import timezone # tarih saat işlemleri için utc formatında evrensel, datetime.datetime.now() kullanınca server saatini alıyo
from django.contrib.auth.models import User

# sonradan değiştirebiliriz örnek olarak oluşturuyorum ben

# EV TABLOSU
class Home(models.Model):
    name = models.CharField(max_length=100, default='My Home')  # oluşturulan evin adı, defaultta My Home
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='homes', null=True)  # User modeli bağlandı
    created_at= models.DateTimeField(auto_now_add=True)
    is_armed = models.BooleanField(default=False)
    alarm_triggered = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
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

    DEVICE_SUB_TYPES = (
        ('SMOKE', 'Duman Sensörü (MQ-2)'),
        ('GAS', 'Gaz Sensörü (MQ-6)'),
        ('WATER', 'Su Baskını Sensörü'),
        ('MOTION', 'Hareket Sensörü (PIR)'),
        ('VIBRATION', 'Titreşim/Deprem Sensörü'),
        ('PUMP', 'Tahliye Pompası'),
        ('BUZZER', 'Sesli Alarm'),
        ('NFC', 'NFC Giriş Modülü'),
        ('MAGNETIC', 'Manyetik Kapı/Pencere Sensörü'),
        ('FLOW', 'Su Akış Sensörü (YF-S201)'),
    )

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=50)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_sub_type = models.CharField(max_length=20, choices=DEVICE_SUB_TYPES, default='SMOKE')
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

# NFC TAG TABLOSU
class NFCTag(models.Model):
    uid = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nfc_tags')
    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='nfc_tags')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.uid} - {self.user.username}"



    
    