from __future__ import annotations

from django.db import models

from shared.models import TimeStampedModel


class WelfareNote(TimeStampedModel):
    """A staff annotation/flag on a personnel's consolidated welfare file."""

    NOTE = "note"
    FLAG = "flag"
    PRIORITY = "priority"
    CATEGORY_CHOICES = [
        (NOTE, "یادداشت"),
        (FLAG, "هشدار"),
        (PRIORITY, "اولویت ویژه"),
    ]

    personnel = models.ForeignKey("hr.Personnel", on_delete=models.CASCADE, related_name="welfare_notes")
    author = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="welfare_notes")
    category = models.CharField("دسته", max_length=10, choices=CATEGORY_CHOICES, default=NOTE, db_index=True)
    text = models.TextField("متن")

    class Meta:
        verbose_name = "یادداشت پروندهٔ رفاهی"
        verbose_name_plural = "یادداشت‌های پروندهٔ رفاهی"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_category_display()} — {self.personnel}"
