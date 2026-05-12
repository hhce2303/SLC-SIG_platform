from django.db import models


class DailyEvent(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_event")
    user = models.ForeignKey(
        "core.User",
        db_column="ID_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="events",
    )
    site = models.ForeignKey(
        "core.Site",
        db_column="ID_site",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="events",
    )
    activity = models.ForeignKey(
        "core.Activity",
        db_column="ID_activity",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="events",
    )
    event_datetime = models.DateTimeField(db_column="event_datetime")
    event_status = models.CharField(max_length=20, db_column="event_status")
    quantity = models.CharField(max_length=45, null=True, blank=True, db_column="event_quantity")
    camera = models.CharField(max_length=45, null=True, blank=True, db_column="event_camera")
    description = models.CharField(max_length=100, null=True, blank=True, db_column="event_description")

    class Meta:
        managed = False
        db_table = "daily_events"
        ordering = ["-event_datetime"]

    def __str__(self) -> str:
        return f"Event #{self.pk} [{self.event_status}]"
