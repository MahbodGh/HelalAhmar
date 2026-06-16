"""Shared kernel: abstract base models reused by every bounded context."""
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """created/updated audit fields (RFP requires full logging everywhere)."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    """Soft delete so 'حذف فقط توسط ستاد با ثبت لاگ' keeps history."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True
