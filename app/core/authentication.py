from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware


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


class JWTWebsocketMiddleware(BaseMiddleware):
    """
    WebSocket bağlantılarında ?token=<jwt> query parametresini doğrular.
    Flutter ve Raspberry Pi bağlanırken token'ı URL'e eklemeli:
      ws://host/ws/alerts/1/?token=<keycloak_access_token>
    """
    async def __call__(self, scope, receive, send):
        from urllib.parse import parse_qs
        query_string = scope.get('query_string', b'').decode()
        token = parse_qs(query_string).get('token', [None])[0]

        scope['user'] = await self._get_user(token)
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _get_user(self, raw_token):
        if not raw_token:
            return AnonymousUser()
        try:
            auth = KeycloakJWTAuthentication()
            validated = auth.get_validated_token(raw_token.encode())
            return auth.get_user(validated)
        except (InvalidToken, TokenError):
            return AnonymousUser()