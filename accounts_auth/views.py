from django.contrib.auth.hashers import check_password
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from central.models import Company, CompanyStatus, DbStatus
from Hatmasewa.db_router import tenant_database_alias


class SSOLoginSerializer(serializers.Serializer):
	org_id = serializers.IntegerField(min_value=1)
	email = serializers.EmailField()
	password = serializers.CharField(write_only=True, trim_whitespace=False)


class SSOLoginView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = SSOLoginSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		company = (
			Company.objects.using("central")
			.select_related("owner", "database")
			.filter(
				org_id=serializer.validated_data["org_id"],
				owner__email__iexact=serializer.validated_data["email"],
				status__in=(CompanyStatus.TRIAL, CompanyStatus.ACTIVE),
			)
			.first()
		)

		if (
			company is None
			or not check_password(serializer.validated_data["password"], company.owner.password_hash)
			or not hasattr(company, "database")
			or company.database.status != DbStatus.READY
		):
			return Response(
				{"detail": "Invalid organization or credentials."},
				status=status.HTTP_401_UNAUTHORIZED,
			)

		refresh = RefreshToken()
		refresh["org_id"] = company.org_id
		refresh["company_id"] = str(company.id)
		refresh["owner_id"] = str(company.owner.id)
		refresh["tenant_database"] = tenant_database_alias(company)
		refresh["email"] = company.owner.email

		return Response(
			{
				"access": str(refresh.access_token),
				"refresh": str(refresh),
				"org_id": company.org_id,
				"company_id": str(company.id),
			}
		)

# Create your views here.
