from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField(db_index=True)),
                ('product_id', models.CharField(max_length=50)),
                ('product_type', models.CharField(max_length=50)),
                ('product_name', models.CharField(max_length=255)),
                ('price', models.FloatField()),
                ('quantity', models.IntegerField(default=1)),
                ('size', models.CharField(blank=True, default='', max_length=50, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('user_id', 'product_id', 'product_type', 'size')},
            },
        ),
    ]
