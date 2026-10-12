from django.db import models
from django.utils import timezone


class TicketQuerySet(models.QuerySet):
    def delete(self):
        """Soft-delete matching tickets while retaining their history."""
        now = timezone.now()
        count = self.filter(deleted_at__isnull=True).update(deleted_at=now, updated_at=now)
        return count, {"tickets.Ticket": count}

    def hard_delete(self):
        return super().delete()


class ActiveTicketManager(models.Manager.from_queryset(TicketQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllTicketManager(models.Manager.from_queryset(TicketQuerySet)):
    pass


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Normal application queries hide deleted records. Use all_objects for
    # auditing or recovery of soft-deleted tickets.
    objects = ActiveTicketManager()
    all_objects = AllTicketManager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"updated_at"}
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(using=using, update_fields=["deleted_at", "updated_at"])
        return 1, {"tickets.Ticket": 1}
