import csv

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from finance.api.serializers import (
    AddItemSerializer,
    DeductionBatchSerializer,
    DeductionItemSerializer,
)
from finance.application import services as app
from finance.models import DeductionBatch
from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission

VIEW = "finance.export.view"


@extend_schema(tags=["finance"])
class DeductionBatchViewSet(viewsets.ModelViewSet):
    """فایل‌های کسورات ماهانه (واحد مالی: finance.export.view)."""

    serializer_class = DeductionBatchSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "delete", "head", "options"]
    permission_classes = [HasPermission.of(VIEW)]

    def get_queryset(self):
        return app.scoped_batches(self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(summary="تولید خودکار اقلام از اقساط وام و حق‌بیمه", responses=DeductionBatchSerializer)
    @action(detail=True, methods=["post"], url_path="generate")
    def generate(self, request, pk=None):
        batch = self.get_object()
        try:
            app.generate_items(batch)
        except app.FinanceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(DeductionBatchSerializer(batch).data)

    @extend_schema(request=AddItemSerializer, responses=DeductionItemSerializer, summary="افزودن قلم دستی")
    @action(detail=True, methods=["post"], url_path="add-item")
    def add_item(self, request, pk=None):
        batch = self.get_object()
        ser = AddItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        from hr.models import Personnel
        personnel = Personnel.objects.filter(id=ser.validated_data["personnel"]).first()
        if personnel is None:
            return Response({"detail": "پرسنل یافت نشد."}, status=400)
        try:
            item = app.add_manual_item(batch, personnel, ser.validated_data["amount"], ser.validated_data.get("description", ""))
        except app.FinanceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(DeductionItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="نهایی‌سازی فایل", responses=DeductionBatchSerializer)
    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        batch = self.get_object()
        try:
            app.finalize(batch)
        except app.FinanceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(DeductionBatchSerializer(batch).data)

    @extend_schema(summary="اقلام فایل (صفحه‌بندی)", responses=DeductionItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, pk=None):
        batch = self.get_object()
        qs = app.scoped_items(request.user, batch)
        page = self.paginate_queryset(qs)
        ser = DeductionItemSerializer(page if page is not None else qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @extend_schema(summary="خروجی CSV فایل کسورات (فایل قابل دانلود)")
    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        batch = self.get_object()
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = f'attachment; filename="deductions_{batch.period}.csv"'
        response.write("\ufeff")  # BOM so Excel reads UTF-8 (Persian) correctly
        writer = csv.writer(response)
        writer.writerow(["ردیف", "شماره پرسنلی", "نام", "منشأ", "مرجع", "مبلغ", "شرح"])
        for i, item in enumerate(app.scoped_items(request.user, batch), start=1):
            writer.writerow([
                i, item.personnel.personnel_no, item.personnel.full_name,
                item.get_source_type_display(), item.source_ref, item.amount, item.description,
            ])
        writer.writerow(["", "", "", "", "جمع کل", batch.total_amount, ""])
        if batch.status == DeductionBatch.FINALIZED:
            app.mark_exported(batch)
        return response
