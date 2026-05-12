from django.db import models


class StationInfo(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_station")
    station_number = models.CharField(max_length=20, db_column="station_number")

    class Meta:
        managed = False
        db_table = "daily_stations_info"

    def __str__(self) -> str:
        return self.station_number


class StationMap(models.Model):
    station = models.OneToOneField(
        StationInfo,
        primary_key=True,
        db_column="station_ID",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="mapping",
    )
    station_user = models.ForeignKey(
        "core.User",
        db_column="station_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="station_assignments",
    )
    is_active = models.IntegerField(null=True, blank=True, db_column="is_active")

    class Meta:
        managed = False
        db_table = "daily_stations_map"

    def __str__(self) -> str:
        return f"Station {self.station_id} -> User {self.station_user_id}"
