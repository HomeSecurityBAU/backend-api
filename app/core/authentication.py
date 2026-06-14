from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware


import jwt
from jwt.algorithms import RSAAlgorithm
import urllib.request
import json
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger("django")

class KeycloakJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        try:
            token_str = raw_token.decode('utf-8') if isinstance(raw_token, bytes) else raw_token
            
            # 1. Decode header to get kid
            header = jwt.get_unverified_header(token_str)
            kid = header.get('kid')
            if not kid:
                raise InvalidToken("Token header does not contain kid")
                
            # 2. Get public key for this kid (cached)
            public_key = self._get_public_key(kid)
            if not public_key:
                raise InvalidToken("Matching JWK public key not found")
                
            # 3. Decode and validate token using PyJWT
            simple_jwt_settings = getattr(settings, 'SIMPLE_JWT', {})
            issuer = simple_jwt_settings.get('ISSUER')
            
            decoded = jwt.decode(
                token_str,
                public_key,
                algorithms=['RS256'],
                options={"verify_aud": False},
                issuer=issuer
            )
            return decoded
        except Exception as e:
            logger.error(f"JWT validation failed: {e}")
            raise InvalidToken(f"Token is invalid or expired: {e}")

    def _get_public_key(self, kid):
        cache_key = f"jwk_public_key_{kid}"
        jwk = cache.get(cache_key)
        if jwk:
            return RSAAlgorithm.from_jwk(jwk)
            
        jwks = self._fetch_jwks()
        if not jwks:
            return None
            
        matching_jwk = None
        for key in jwks.get('keys', []):
            current_kid = key.get('kid')
            if current_kid:
                cache.set(f"jwk_public_key_{current_kid}", key, timeout=86400)
                if current_kid == kid:
                    matching_jwk = key
                    
        if matching_jwk:
            return RSAAlgorithm.from_jwk(matching_jwk)
        return None

    def _fetch_jwks(self):
        jwks = cache.get("raw_jwks_data")
        if jwks:
            return jwks
            
        simple_jwt_settings = getattr(settings, 'SIMPLE_JWT', {})
        jwk_url = simple_jwt_settings.get('JWK_URL')
        if not jwk_url:
            logger.error("SIMPLE_JWT['JWK_URL'] settings is not configured")
            return None
            
        try:
            req = urllib.request.Request(jwk_url, headers={"User-Agent": "Django-Keycloak-Client"})
            with urllib.request.urlopen(req, timeout=4) as response:
                jwks = json.loads(response.read().decode('utf-8'))
                cache.set("raw_jwks_data", jwks, timeout=300)
                return jwks
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from Keycloak server: {e}")
            return None

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