
## views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from accounts.models import Payment
from accounts.permissions import IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive
from accounts.serializers import (
    PaymentCreateSerializer,
    PaymentUpdateSerializer,
    PaymentDeleteSerializer,
    PaymentFilterInputSerializer,
    PaymentListSerializer
)
from django.db import transaction
from django.conf import settings

class PaymentCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]

    @transaction.atomic    
    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            payment = serializer.save()
            return Response(PaymentListSerializer(payment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PaymentUpdateAPIView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]
    

    def put(self, request, payment_id):
        payment = get_object_or_404(Payment, payment_id=payment_id, user=request.user)
        serializer = PaymentUpdateSerializer(payment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(PaymentListSerializer(payment).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PaymentDeleteAPIView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]
    

    def delete(self, request, payment_id):
        payment = get_object_or_404(Payment, payment_id=payment_id, user=request.user)
        payment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class PaymentListAPIView(APIView):
    permission_classes = [IsAuthenticatedViaLoginSession, IsGymOwnerOrStaff, IsCheckUserActive]
    

    def post(self, request):
        # input payload has start_date, end_date, user_ids
        filter_serializer = PaymentFilterInputSerializer(data=request.data)
        if not filter_serializer.is_valid():
            return Response(filter_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        start_date = filter_serializer.validated_data['start_date']
        end_date = filter_serializer.validated_data['end_date']
        user_ids = filter_serializer.validated_data.get('user_ids', [])
        qs = Payment.objects.filter(payment_date__date__gte=start_date,
                                    payment_date__date__lte=end_date)
        if user_ids:
            qs = qs.filter(user__in=user_ids)
        payments = qs.order_by('-payment_date')
        out = PaymentListSerializer(payments, many=True)
        return Response(out.data)

    def get(self, request):
        # List all payments for the authenticated user
        payments = Payment.objects.all().order_by('-payment_date')
        serializer = PaymentListSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)