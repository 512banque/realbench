<?php

namespace Database\Factories;

use App\Models\Product;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Product>
 */
class ProductFactory extends Factory
{
    protected $model = Product::class;

    public function definition(): array
    {
        return [
            'name' => $this->faker->words(2, true),
            'price_cents' => $this->faker->numberBetween(500, 5000),
            'stock' => $this->faker->numberBetween(10, 100),
        ];
    }
}
