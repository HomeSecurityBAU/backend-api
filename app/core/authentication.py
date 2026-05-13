from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User

class KeycloakJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        # Keycloak token'ı içerisindeki payload alanlarını alıyoruz
        username = validated_token.get('preferred_username')
        email = validated_token.get('email', '')
        given_name = validated_token.get('given_name', '')
        family_name = validated_token.get('family_name', '')

        if not username:
            return None

        # Kullanıcıyı veritabanında ara, bulamazsan yeni oluştur
        user, created = User.objects.get_or_create(username=username)

        if created:
            user.email = email
            user.first_name = given_name
            user.last_name = family_name
            user.set_unusable_password()  # Şifreler Django'da saklanmayacak, kimlik doğrulama Keycloak'ta yapılıyor
            user.save()

        return user