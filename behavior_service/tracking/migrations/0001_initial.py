from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='SearchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField(blank=True, null=True)),
                ('query_text', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='InteractionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField(blank=True, null=True)),
                ('product_id', models.CharField(max_length=50)),
                ('product_type', models.CharField(max_length=20)),
                ('action_type', models.CharField(choices=[('search', 'Search'), ('click', 'Click/View'), ('view', 'View'), ('add_to_cart', 'Add to Cart'), ('purchase', 'Purchase'), ('chat', 'Chat'), ('remove_from_cart', 'Remove from Cart')], max_length=20)),
                ('session_id', models.CharField(blank=True, max_length=50, null=True)),
                ('device', models.CharField(blank=True, max_length=20, null=True)),
                ('region', models.CharField(blank=True, max_length=20, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
