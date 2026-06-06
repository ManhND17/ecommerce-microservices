from django.db import migrations, models


def populate_cart_for_existing_items(apps, schema_editor):
    Cart = apps.get_model('cart', 'Cart')
    CartItem = apps.get_model('cart', 'CartItem')
    db_alias = schema_editor.connection.alias

    for item in CartItem.objects.using(db_alias).all():
        cart, _ = Cart.objects.using(db_alias).get_or_create(user_id=item.user_id)
        item.cart_id = cart.id
        item.save(update_fields=['cart_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0002_cartitem_image_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField(db_index=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='cartitem',
            name='cart',
            field=models.ForeignKey(null=True, on_delete=models.CASCADE, related_name='items', to='cart.cart'),
        ),
        migrations.RunPython(populate_cart_for_existing_items, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cartitem',
            name='cart',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='items', to='cart.cart'),
        ),
        migrations.AlterUniqueTogether(
            name='cartitem',
            unique_together={('cart', 'product_id', 'product_type', 'size')},
        ),
    ]
