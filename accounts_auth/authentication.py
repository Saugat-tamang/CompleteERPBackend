from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from central.models import CompanyOwner


class CompanyOwnerJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        owner_id = validated_token.get("owner_id")
        if owner_id is None:
            raise AuthenticationFailed("Token does not identify an organization owner.")

        owner = CompanyOwner.objects.using("central").filter(id=owner_id).first()
        if owner is None:
            raise AuthenticationFailed("Organization owner no longer exists.")

        return owner, validated_token