from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin

from .models import Refund
from .serializers import (
    RefundCreateSerializer,
    RefundSerializer,
    RefundCompleteSerializer,
    RefundFailSerializer,
)
from .services import RefundService


class RefundListCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        refunds = (
            Refund.objects
            .select_related(
                "payment",
                "payment__order",
                "processed_by",
            )
            .all()
        )

        serializer = RefundSerializer(refunds, many=True)

        return Response(serializer.data)

    def post(self, request):
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund = RefundService.create_refund(
            payment_id=serializer.validated_data["payment_id"],
            amount=serializer.validated_data["amount"],
            refund_method=serializer.validated_data["refund_method"],
            admin_user=request.user,
            admin_note=serializer.validated_data.get("admin_note", ""),
        )

        return Response(
            {
                "message": "Refund created successfully.",
                "refund": RefundSerializer(refund).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RefundProcessView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        refund = RefundService.start_refund(
            refund_id=pk,
            admin_user=request.user,
        )

        return Response(
            {
                "message": "Refund moved to processing.",
                "refund": RefundSerializer(refund).data,
            },
            status=status.HTTP_200_OK,
        )


class RefundCompleteView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        serializer = RefundCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund = RefundService.complete_refund(
            refund_id=pk,
            transaction_reference=serializer.validated_data[
                "transaction_reference"
            ],
            admin_user=request.user,
            admin_note=serializer.validated_data.get("admin_note"),
        )

        return Response(
            {
                "message": "Refund completed successfully.",
                "refund": RefundSerializer(refund).data,
            },
            status=status.HTTP_200_OK,
        )


class RefundFailView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        serializer = RefundFailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund = RefundService.fail_refund(
            refund_id=pk,
            admin_user=request.user,
            admin_note=serializer.validated_data.get("admin_note", ""),
        )

        return Response(
            {
                "message": "Refund marked as failed.",
                "refund": RefundSerializer(refund).data,
            },
            status=status.HTTP_200_OK,
        )