<?php

namespace Database\Factories;

use App\Models\Order;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Order>
 */
class OrderFactory extends Factory
{
    protected $model = Order::class;

    public function definition(): array
    {
        return [
            'user_id' => User::factory(),
            'subtotal_cents' => 0,
            'tax_cents' => 0,
            'discount_cents' => 0,
            'total_cents' => 0,
            'status' => 'pending',
        ];
    }
}
