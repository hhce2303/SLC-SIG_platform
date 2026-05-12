from django.db import models


class Special(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_special")
    event = models.ForeignKey(
        "logs.DailyEvent",
        db_column="ID_event",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="specials",
    )
    site = models.ForeignKey(
        "core.Site",
        db_column="ID_site",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="specials",
    )
    activity = models.ForeignKey(
        "core.Activity",
        db_column="ID_activity",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="specials",
    )
    user = models.ForeignKey(
        "core.User",
        db_column="ID_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="specials_created",
    )
    supervisor = models.ForeignKey(
        "core.User",
        db_column="ID_supervisor",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="specials_assigned",
    )
    spec_datetime = models.DateTimeField(db_column="spec_datetime")
    spec_quantity = models.CharField(max_length=45, null=True, blank=True, db_column="spec_quantity")
    spec_camera = models.CharField(max_length=45, null=True, blank=True, db_column="spec_camera")
    spec_status = models.CharField(
        max_length=20, null=True, blank=True, db_column="spec_status"
    )
    spec_description = models.TextField(null=True, blank=True, db_column="spec_description")
    spec_marked_at = models.DateTimeField(null=True, blank=True, db_column="spec_marked_at")
    spec_marked_by = models.IntegerField(null=True, blank=True, db_column="spec_marked_by")

    class Meta:
        managed = False
        db_table = "daily_specials"

    def __str__(self) -> str:
        return f"Special #{self.pk} [{self.spec_status or 'pending'}]"


class News(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_news")
    news_type = models.CharField(max_length=50, db_column="news_type")
    news_info = models.TextField(db_column="news_info")
    news_urgency = models.CharField(max_length=20, db_column="news_urgency")
    news_datetime_in = models.DateTimeField(db_column="news_datetime_in")
    news_datetime_out = models.DateTimeField(
        null=True, blank=True, db_column="news_datetime_out"
    )
    active = models.IntegerField(default=1, db_column="active")

    class Meta:
        managed = False
        db_table = "daily_news"

    def __str__(self) -> str:
        return f"News #{self.pk} [{self.news_type}]"
