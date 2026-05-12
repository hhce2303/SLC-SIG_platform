from django.db import models


class Session(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_sesion")
    user = models.ForeignKey(
        "core.User",
        db_column="ID_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="sessions",
    )
    station = models.ForeignKey(
        "core.StationInfo",
        db_column="ID_station",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="sessions",
    )
    sesion_in = models.DateTimeField(db_column="sesion_in")
    sesion_out = models.DateTimeField(null=True, blank=True, db_column="sesion_Out")
    sesion_active = models.IntegerField(default=1, db_column="sesion_active")
    sesion_status = models.IntegerField(default=0, db_column="sesion_status")

    class Meta:
        managed = False
        db_table = "daily_sesions"

    def __str__(self) -> str:
        return f"Session #{self.pk} user={self.user_id} active={self.sesion_active}"


class CoverRequest(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_cover")
    user = models.ForeignKey(
        "core.User",
        db_column="ID_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="cover_requests",
    )
    cover_time_request = models.DateTimeField(db_column="cover_time_request")
    station = models.ForeignKey(
        "core.StationInfo",
        db_column="ID_station",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="cover_requests",
    )
    approved = models.IntegerField(default=0, db_column="approved")
    active = models.IntegerField(default=1, db_column="active")

    class Meta:
        managed = False
        db_table = "daily_covers_solicitudes"


class CoverCompleted(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_cover_complete")
    user = models.ForeignKey(
        "core.User",
        db_column="ID_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="covers_received",
    )
    cover_by = models.ForeignKey(
        "core.User",
        db_column="ID_user_cover_by",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="covers_given",
    )
    cover_in = models.DateTimeField(db_column="cover_in")
    cover_out = models.DateTimeField(null=True, blank=True, db_column="cover_out")

    class Meta:
        managed = False
        db_table = "daily_covers_completed"


class Break(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_break")
    user_covered = models.ForeignKey(
        "core.User",
        db_column="ID_user_covered",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="breaks_received",
    )
    user_covering = models.ForeignKey(
        "core.User",
        db_column="ID_user_covering",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="breaks_given",
    )
    break_datetime = models.DateTimeField(db_column="break_datetime")
    active = models.IntegerField(default=1, db_column="active")
    supervisor = models.ForeignKey(
        "core.User",
        db_column="ID_supervisor",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="breaks_supervised",
    )
    break_creation = models.DateTimeField(null=True, blank=True, db_column="break_creation")

    class Meta:
        managed = False
        db_table = "daily_breaks"
