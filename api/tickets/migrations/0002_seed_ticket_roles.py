from django.db import migrations


ROLE_PERMISSIONS = {
    "Admin": ("view_ticket", "add_ticket", "change_ticket", "delete_ticket"),
    "Agent": ("view_ticket", "add_ticket", "change_ticket"),
    "Viewer": ("view_ticket",),
}


def create_ticket_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    database = schema_editor.connection.alias

    content_type, _ = ContentType.objects.using(database).get_or_create(
        app_label="tickets",
        model="ticket",
    )
    ticket_permissions = {}
    permission_names = {
        "view_ticket": "Can view ticket",
        "add_ticket": "Can add ticket",
        "change_ticket": "Can change ticket",
        "delete_ticket": "Can delete ticket",
    }
    for codename, name in permission_names.items():
        permission, _ = Permission.objects.using(database).get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": name},
        )
        ticket_permissions[codename] = permission

    for role, codenames in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.using(database).get_or_create(name=role)
        group.permissions.set(ticket_permissions[codename] for codename in codenames)


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("tickets", "0001_initial"),
    ]

    operations = [migrations.RunPython(create_ticket_roles, migrations.RunPython.noop)]
