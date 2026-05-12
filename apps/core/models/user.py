from django.db import models


class UserRole(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_user_rol")
    name = models.CharField(max_length=50, db_column="user_rol_name")

    class Meta:
        managed = False
        db_table = "daily_user_rol"

    def __str__(self) -> str:
        return self.name


class User(models.Model):
    id = models.AutoField(primary_key=True, db_column="ID_user")
    password = models.CharField(max_length=255, db_column="user_password")
    role = models.ForeignKey(
        UserRole,
        db_column="ID_user_rol",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="users",
    )

    class Meta:
        managed = False
        db_table = "daily_users"

    def __str__(self) -> str:
        name = getattr(self, "_cached_name", None)
        if name is None:
            try:
                name = self.profile.user_name
            except UserName.DoesNotExist:
                name = f"User #{self.pk}"
            self._cached_name = name
        return name


class UserName(models.Model):
    user = models.OneToOneField(
        User,
        primary_key=True,
        db_column="ID_user",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="profile",
    )
    user_name = models.CharField(max_length=100, db_column="user_name")

    class Meta:
        managed = False
        db_table = "daily_users_names"

    def __str__(self) -> str:
        return self.user_name
