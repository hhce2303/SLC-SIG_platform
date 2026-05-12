from django.db import models


class Site(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_site")
    group_id = models.CharField(max_length=45, db_column="ID_group")
    site_name = models.CharField(max_length=200, db_column="site_name")
    site_dns = models.CharField(max_length=200, null=True, blank=True, db_column="site_dns")
    site_timezone = models.CharField(max_length=50, null=True, blank=True, db_column="site_timezone")

    class Meta:
        managed = False
        db_table = "daily_sites"

    def __str__(self) -> str:
        return self.site_name


class Activity(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_activity")
    act_name = models.CharField(max_length=200, db_column="act_name")

    class Meta:
        managed = False
        db_table = "daily_activities"

    def __str__(self) -> str:
        return self.act_name


class SpecialGroup(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_site_special")
    group_code = models.CharField(max_length=5, db_column="site_group_special")

    class Meta:
        managed = False
        db_table = "daily_special_groups"

    def __str__(self) -> str:
        return self.group_code


class SeasonConfig(models.Model):
    """
    Stores the currently active season (winter / summer).
    Only one row should have active=1 at a time.

    Table: daily_season_offsets
    Columns: ID_season (PK), season_offsets (str), active (tinyint)
    """

    id = models.AutoField(primary_key=True, db_column="ID_season")
    season_offsets = models.CharField(max_length=20, db_column="season_offsets")
    active = models.SmallIntegerField(db_column="active")

    class Meta:
        managed = False
        db_table = "daily_season_offsets"

    def __str__(self) -> str:
        return f"{self.season_offsets} (active={self.active})"


class WinterOffset(models.Model):
    """
    Hour offset (relative to Colombia time) per US timezone during Winter.

    Table: daily_winter_offsets
    Columns: ID_time_offset (PK), time_zone (str), time_offset (int)
    """

    id = models.AutoField(primary_key=True, db_column="ID_time_offset")
    time_zone = models.CharField(max_length=5, db_column="time_zone")
    time_offset = models.IntegerField(db_column="time_offset")

    class Meta:
        managed = False
        db_table = "daily_winter_offsets"

    def __str__(self) -> str:
        return f"{self.time_zone} ({self.time_offset:+.2f}h) [winter]"


class SummerOffset(models.Model):
    """
    Hour offset (relative to Colombia time) per US timezone during Summer (DST).

    Table: daily_summer_offsets
    Columns: ID_time_offset (PK), time_zone (str), time_offset (int)
    """

    id = models.AutoField(primary_key=True, db_column="ID_time_offset")
    time_zone = models.CharField(max_length=5, db_column="time_zone")
    time_offset = models.IntegerField(db_column="time_offset")

    class Meta:
        managed = False
        db_table = "daily_summer_offsets"

    def __str__(self) -> str:
        return f"{self.time_zone} ({self.time_offset:+.2f}h) [summer]"
